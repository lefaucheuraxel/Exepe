from flask import Flask, render_template, request, jsonify, session, send_file, redirect, url_for
import csv
import os
import uuid
import datetime
import random
import threading
from werkzeug.utils import secure_filename
import io
import subprocess
import base64
import requests

#Flask
app = Flask(__name__)
app.secret_key = 'experience_perception_mots_couleurs_2024'

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RESULTS_FILE = os.path.join(DATA_DIR, 'results.csv')
RESULTS_LOCK = threading.Lock()

# Mots réels français
REAL_WORDS = [
    "chien", "chat", "maison", "voiture", "pomme", "livre", "plage", "arbre", 
    "soleil", "lune", "fleur", "oiseau", "poisson", "montagne", "rivière", 
    "forêt", "table", "chaise", "fenêtre", "porte", "jardin", "école", 
    "hôpital", "magasin"
]

# Non-mots avec lettres complètement aléatoires
FAKE_WORDS = [
    "blixor", "frunez", "glopek", "tralux", "vokrim", "zephiq", "quilmex", 
    "braxon", "flumig", "krenov", "doltex", "prixel", "vextor", "glumix", 
    "tronez", "blefox", "krimol", "floxen", "vraliq", "gextom", "pluvex", 
    "drixel", "blomek", "kraxon"
]

# Données de l'expérience
WORDS = REAL_WORDS
NON_WORDS = FAKE_WORDS
ALL_STIMULI = WORDS + NON_WORDS
DISPLAY_TIME = 50  # ms

SIMILAR_DISTRACTORS = {}

COLOR_ASSOCIATED_WORDS = {
    "rouge": ["sang", "tomate", "rose", "cerise", "feu"],
    "vert": ["herbe", "salade", "forêt", "nature", "pomme"],
    "bleu": ["ciel", "mer", "océan", "bleuet", "saphir"],
    "violet": ["lavande", "prune", "aubergine", "lilas", "améthyste"],
    "orange": ["carotte", "citrouille", "abricot", "mandarine", "flamme"],
}

COLORS = {
    "rouge": "#FF0000",
    "vert": "#00C800", 
    "bleu": "#0000FF",
    "violet": "#8B00FF",
    "orange": "#FF6600",
}

BACKGROUND_COLORS = [
    "#FF4444",  # rouge vif
    "#44FF44",  # vert vif
    "#4444FF",  # bleu vif
    "#FF44FF",  # magenta vif
    "#44FFFF",  # cyan vif
    "#FF8800",  # orange vif
    "#8844FF",  # violet vif
]

def hex_to_rgb(hex_color):
    """Convertit une couleur hexadécimale en RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def color_distance(color1, color2):
    """Calcule la distance euclidienne entre deux couleurs RGB."""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    return ((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2)**0.5

def colors_too_similar(color1, color2, threshold=100):
    """Vérifie si deux couleurs sont trop similaires."""
    return color_distance(color1, color2) < threshold

def is_light_color(hex_color):
    """Détermine si une couleur est claire (pour choisir noir ou blanc)."""
    r, g, b = hex_to_rgb(hex_color)
    # Formule de luminance
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return luminance > 128

def recover_results_from_git():
    """Récupère le fichier results.csv depuis Git si absent localement."""
    if os.path.exists(RESULTS_FILE):
        return  # Fichier existe déjà
    
    try:
        # Vérifier que nous sommes dans un repo git
        subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        
        # Essayer de récupérer le fichier depuis Git
        result = subprocess.run(
            ['git', 'show', 'HEAD:data/results.csv'],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Créer le dossier s'il n'existe pas
            os.makedirs(DATA_DIR, exist_ok=True)
            # Écrire le fichier récupéré
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            print(f"✅ Fichier results.csv récupéré depuis Git ({len(result.stdout)} bytes)")
            return
    except Exception as e:
        print(f"ℹ️ Impossible de récupérer results.csv depuis Git: {e}")
    
    try:
        owner = os.environ.get('GITHUB_OWNER')
        repo = os.environ.get('GITHUB_REPO')
        branch = os.environ.get('GITHUB_BRANCH', 'main')
        token = os.environ.get('GITHUB_TOKEN')
        if owner and repo and branch:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/data/results.csv"
            headers = {}
            if token:
                headers['Authorization'] = f"Bearer {token}"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200 and resp.text:
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                    f.write(resp.text)
                print("✅ Fichier results.csv récupéré via GitHub raw")
                return
    except Exception as e:
        print(f"ℹ️ Impossible de récupérer results.csv via GitHub raw: {e}")

def init_csv():
    """Initialise le fichier CSV avec les en-têtes si il n'existe pas."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Migration: déplacer l'ancien results.csv (racine) vers data/results.csv si présent
    try:
        legacy_path = os.path.join(BASE_DIR, 'results.csv')
        if not os.path.exists(RESULTS_FILE) and os.path.exists(legacy_path):
            os.replace(legacy_path, RESULTS_FILE)
            print("ℹ️ Fichier results.csv migré vers data/results.csv")
    except Exception as _e:
        pass
    
    # Migration: renommer un ancien fichier data/experience_results.csv en data/results.csv
    try:
        legacy_exp_path = os.path.join(DATA_DIR, 'experience_results.csv')
        if not os.path.exists(RESULTS_FILE) and os.path.exists(legacy_exp_path):
            os.replace(legacy_exp_path, RESULTS_FILE)
            print("ℹ️ Fichier experience_results.csv migré vers data/results.csv")
            # Committer la migration pour persister côté Git si auto-commit actif
            try:
                commit_results_async("Migrate experience_results.csv to data/results.csv", force_commit=True)
            except Exception:
                pass
    except Exception as _e:
        pass
    
    # Essayer de récupérer depuis Git si le fichier n'existe pas
    if not os.path.exists(RESULTS_FILE):
        recover_results_from_git()
    
    # Créer le fichier s'il n'existe toujours pas
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'session_id', 'participant_id', 'timestamp', 'trial_number', 'block_type',
                'stimulus', 'response', 'correct', 'reaction_time', 'text_color', 
                'background_color', 'is_word', 'choices_presented'
            ])
        print(f"✅ Nouveau fichier CSV créé: {RESULTS_FILE}")

def save_result(session_id, participant_id, trial_data):
    """Sauvegarde un résultat dans le fichier CSV de manière thread-safe."""
    with RESULTS_LOCK:
        # S'assurer que le fichier existe
        init_csv()
        
        with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Gérer les choix (peut être une liste ou None)
            choices_str = ''
            if 'choices' in trial_data and trial_data['choices']:
                if isinstance(trial_data['choices'], list):
                    choices_str = '|'.join(trial_data['choices'])
                else:
                    choices_str = str(trial_data['choices'])
            
            writer.writerow([
                session_id,
                participant_id,
                trial_data.get('timestamp', datetime.datetime.now().isoformat()),
                trial_data.get('trial_number', ''),
                trial_data.get('block_type', ''),
                trial_data.get('stimulus', ''),
                trial_data.get('response', ''),
                trial_data.get('correct', False),
                trial_data.get('reaction_time', 0),
                trial_data.get('text_color', '#000000'),
                trial_data.get('background_color', '#ffffff'),
                trial_data.get('is_word', False),
                choices_str
            ])
            f.flush()
            os.fsync(f.fileno())
            
        print(f"✅ Résultat sauvegardé: {participant_id[:8]}... - {trial_data.get('stimulus', 'N/A')} - {trial_data.get('correct', 'N/A')}")
    # Lancer un commit git asynchrone (n'impacte pas la réponse HTTP)
    commit_message = (
        f"Add result trial={trial_data.get('trial_number','')} "
        f"block={trial_data.get('block_type','')} stimulus={trial_data.get('stimulus','')}"
    )
    # Sur Render: forcer le push synchrone pour éviter la perte de données lors de la mise en veille
    if str(os.environ.get('AUTO_PUSH_RESULTS', '0')).lower() in ('1', 'true', 'yes'):
        commit_results_sync(commit_message)
    else:
        commit_results_async(commit_message)

def commit_results_sync(message: str = 'Update results.csv', force_commit: bool = False):
    """Effectue un git add/commit/push de data/results.csv de manière SYNCHRONE (bloquante).
    Utilisé sur Render pour garantir la persistance avant mise en veille.
    Désactivable via AUTO_COMMIT_RESULTS=0 dans l'environnement."""
    if str(os.environ.get('AUTO_COMMIT_RESULTS', '1')).lower() in ('0', 'false', 'no'):
        return
    
    try:
        rel_path = os.path.relpath(RESULTS_FILE, BASE_DIR)
        gh_token = os.environ.get('GITHUB_TOKEN')
        gh_owner = os.environ.get('GITHUB_OWNER')
        gh_repo = os.environ.get('GITHUB_REPO')
        gh_branch = os.environ.get('GITHUB_BRANCH', 'main')
        
        # Priorité: push via GitHub API (plus fiable sur Render)
        if gh_token and gh_owner and gh_repo:
            print(f"ℹ️ Tentative push GitHub API (sync) vers {gh_owner}/{gh_repo}/{gh_branch}")
            try:
                path = 'data/results.csv'
                get_url = f"https://api.github.com/repos/{gh_owner}/{gh_repo}/contents/{path}?ref={gh_branch}"
                put_url = f"https://api.github.com/repos/{gh_owner}/{gh_repo}/contents/{path}"
                headers = {
                    'Authorization': f'Bearer {gh_token}',
                    'Accept': 'application/vnd.github+json'
                }
                sha = None
                r = requests.get(get_url, headers=headers, timeout=10)
                if r.status_code == 200 and isinstance(r.json(), dict):
                    sha = r.json().get('sha')
                    print(f"ℹ️ SHA récupéré: {sha[:8]}...")
                with open(RESULTS_FILE, 'rb') as rf:
                    content_b64 = base64.b64encode(rf.read()).decode('ascii')
                payload = {
                    'message': message,
                    'content': content_b64,
                    'branch': gh_branch,
                    'committer': {'name': 'Results Bot', 'email': 'results-bot@local'}
                }
                if sha:
                    payload['sha'] = sha
                pr = requests.put(put_url, headers=headers, json=payload, timeout=20)
                if pr.status_code in (200, 201):
                    print(f"✅ Données pushées vers GitHub (sync): {message}")
                    return
                else:
                    print(f"⚠️ Premier PUT échoué ({pr.status_code}), retry...")
                    # Retry: récupérer le SHA et réessayer
                    r2 = requests.get(get_url, headers=headers, timeout=10)
                    if r2.status_code == 200 and isinstance(r2.json(), dict):
                        payload['sha'] = r2.json().get('sha')
                        pr2 = requests.put(put_url, headers=headers, json=payload, timeout=20)
                        if pr2.status_code in (200, 201):
                            print(f"✅ Données pushées vers GitHub (sync, retry): {message}")
                            return
                        else:
                            print(f"⚠️ Push GitHub échoué (sync, retry): {pr2.status_code}")
                    else:
                        print(f"⚠️ Récupération SHA échouée (retry): {r2.status_code}")
            except Exception as e:
                print(f"⚠️ Push GitHub exception (sync): {e}")
        else:
            print(f"ℹ️ GitHub API non configuré (token={bool(gh_token)}, owner={bool(gh_owner)}, repo={bool(gh_repo)})")
        
        # Fallback: git push local
        try:
            subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            subprocess.run(
                ['git', 'add', rel_path],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            commit_args = ['git', '-c', 'user.email=results-bot@local', '-c', 'user.name=Results Bot', 'commit', '-m', message]
            if force_commit:
                commit_args.append('--allow-empty')
            commit_proc = subprocess.run(
                commit_args,
                cwd=BASE_DIR,
                capture_output=True,
                text=True
            )
            if commit_proc.returncode == 0:
                print(f"✅ Commit effectué (sync): {message}")
                pull_proc = subprocess.run(['git', 'pull', '--rebase'], cwd=BASE_DIR, capture_output=True, text=True, timeout=10)
                print(f"ℹ️ Git pull: {pull_proc.stdout or pull_proc.stderr}")
                push_proc = subprocess.run(['git', 'push'], cwd=BASE_DIR, capture_output=True, text=True, timeout=10)
                if push_proc.returncode == 0:
                    print(f"✅ Données pushées vers le remote (sync)")
                else:
                    print(f"⚠️ Git push échoué: {push_proc.stderr}")
            else:
                print(f"ℹ️ Pas de changements à committer ou erreur: {commit_proc.stderr}")
        except Exception as e:
            print(f"⚠️ Commit/push local échoué (sync): {e}")
    except Exception as e:
        print(f"⚠️ commit_results_sync échoué: {e}")

def commit_results_async(message: str = 'Update results.csv', force_commit: bool = False):
    """Effectue un git add/commit de data/results.csv en tâche de fond.
    Désactivable via AUTO_COMMIT_RESULTS=0 dans l'environnement.
    Optionnellement, pousse sur le remote si AUTO_PUSH_RESULTS=1 (best-effort).
    Si force_commit=True, force le commit même s'il n'y a pas de changements."""
    if str(os.environ.get('AUTO_COMMIT_RESULTS', '1')).lower() in ('0', 'false', 'no'):
        return

    def _worker():
        try:
            rel_path = os.path.relpath(RESULTS_FILE, BASE_DIR)

            # Tentative de push via GitHub API si configuré
            auto_push = str(os.environ.get('AUTO_PUSH_RESULTS', '0')).lower() in ('1', 'true', 'yes')
            gh_token = os.environ.get('GITHUB_TOKEN')
            gh_owner = os.environ.get('GITHUB_OWNER')
            gh_repo = os.environ.get('GITHUB_REPO')
            gh_branch = os.environ.get('GITHUB_BRANCH', 'main')
            used_github_api = False
            if auto_push and gh_token and gh_owner and gh_repo:
                try:
                    path = 'data/results.csv'
                    get_url = f"https://api.github.com/repos/{gh_owner}/{gh_repo}/contents/{path}?ref={gh_branch}"
                    put_url = f"https://api.github.com/repos/{gh_owner}/{gh_repo}/contents/{path}"
                    headers = {
                        'Authorization': f'Bearer {gh_token}',
                        'Accept': 'application/vnd.github+json'
                    }
                    sha = None
                    r = requests.get(get_url, headers=headers, timeout=10)
                    if r.status_code == 200 and isinstance(r.json(), dict):
                        sha = r.json().get('sha')
                    with open(RESULTS_FILE, 'rb') as rf:
                        content_b64 = base64.b64encode(rf.read()).decode('ascii')
                    payload = {
                        'message': message,
                        'content': content_b64,
                        'branch': gh_branch,
                        'committer': {'name': 'Results Bot', 'email': 'results-bot@local'}
                    }
                    if sha:
                        payload['sha'] = sha
                    pr = requests.put(put_url, headers=headers, json=payload, timeout=20)
                    if pr.status_code in (200, 201):
                        print("✅ Données pushées vers GitHub")
                        used_github_api = True
                    else:
                        try:
                            r2 = requests.get(get_url, headers=headers, timeout=10)
                            if r2.status_code == 200 and isinstance(r2.json(), dict):
                                payload['sha'] = r2.json().get('sha')
                                pr2 = requests.put(put_url, headers=headers, json=payload, timeout=20)
                                if pr2.status_code in (200, 201):
                                    print("✅ Données pushées vers GitHub")
                                    used_github_api = True
                                else:
                                    print(f"⚠️ Push GitHub échoué: {pr2.status_code}")
                            else:
                                print(f"⚠️ Récupération SHA GitHub échouée: {r2.status_code}")
                        except Exception:
                            print("⚠️ Retry push GitHub échoué")
                except Exception as e:
                    print(f"⚠️ Push GitHub exception: {e}")

            # Commit local via git si repo présent (utile en dev local)
            try:
                subprocess.run(
                    ['git', 'rev-parse', '--is-inside-work-tree'],
                    cwd=BASE_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                subprocess.run(
                    ['git', 'add', rel_path],
                    cwd=BASE_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                commit_args = ['git', '-c', 'user.email=results-bot@local', '-c', 'user.name=Results Bot', 'commit', '-m', message]
                if force_commit:
                    commit_args.append('--allow-empty')
                commit_proc = subprocess.run(
                    commit_args,
                    cwd=BASE_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if commit_proc.returncode == 0:
                    print(f"✅ Commit effectué: {message}")
                    if auto_push and not used_github_api:
                        try:
                            subprocess.run(['git', 'pull', '--rebase'], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                            subprocess.run(['git', 'push'], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                            print(f"✅ Données pushées vers le remote")
                        except Exception as push_error:
                            print(f"⚠️ Push échoué: {push_error}")
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ Auto-commit échoué: {e}")

    threading.Thread(target=_worker, daemon=True).start()

def get_choices(correct_stimulus, n=4, with_color_word=False):
    """Génère des choix cohérents : mots avec mots, non-mots avec non-mots."""
    choices = [correct_stimulus]
    
    # Déterminer si le stimulus est un mot ou un non-mot
    is_word = correct_stimulus in WORDS
    
    # Choisir la liste appropriée pour les distracteurs
    if is_word:
        available_stimuli = [w for w in WORDS if w != correct_stimulus]
        print(f"🔤 Stimulus '{correct_stimulus}' est un MOT - choix parmi les mots")
    else:
        available_stimuli = [w for w in NON_WORDS if w != correct_stimulus]
        print(f"🔤 Stimulus '{correct_stimulus}' est un NON-MOT - choix parmi les non-mots")
    
    color_names = ["rouge", "vert", "bleu", "violet", "orange", "rose", "magenta", "cyan", "turquoise", "indigo"]
    potential_distractors = []
    
    # 1. Ajouter des distracteurs très similaires (même catégorie)
    if correct_stimulus in SIMILAR_DISTRACTORS:
        similar = [w for w in SIMILAR_DISTRACTORS[correct_stimulus] if w != correct_stimulus and w in available_stimuli]
        potential_distractors.extend(similar[:2])
    
    # 2. NE PLUS mélanger mots et non-mots - garder la cohérence
    
    # 3. Mots associés aux couleurs (seulement si c'est un mot)
    if with_color_word and is_word:
        for color_word_list in COLOR_ASSOCIATED_WORDS.values():
            color_words = [w for w in color_word_list if w != correct_stimulus and w in available_stimuli]
            potential_distractors.extend(color_words[:1])
        
        available_colors = [c for c in color_names if c != correct_stimulus and c in available_stimuli]
        potential_distractors.extend(available_colors[:1])
    
    # 4. Stimuli similaires visuellement (même catégorie)
    same_length = [w for w in available_stimuli if len(w) == len(correct_stimulus)]
    similar_visual = []
    for word in same_length:
        common_letters = sum(1 for i, char in enumerate(word) if i < len(correct_stimulus) and char == correct_stimulus[i])
        if common_letters >= 2:
            similar_visual.append(word)
    potential_distractors.extend(similar_visual[:2])
    
    # 5. Mots qui commencent/finissent pareil (même catégorie)
    if len(correct_stimulus) >= 3:
        same_start = [w for w in available_stimuli if len(w) >= 3 and w[:2] == correct_stimulus[:2]]
        same_end = [w for w in available_stimuli if len(w) >= 3 and w[-2:] == correct_stimulus[-2:]]
        potential_distractors.extend(same_start[:1])
        potential_distractors.extend(same_end[:1])
    
    # Supprimer les doublons
    seen = set([correct_stimulus])
    unique_distractors = []
    for item in potential_distractors:
        if item not in seen:
            unique_distractors.append(item)
            seen.add(item)
    
    # Sélectionner exactement n-1 distracteurs (même catégorie)
    if len(unique_distractors) >= n-1:
        selected_distractors = random.sample(unique_distractors, n-1)
    else:
        selected_distractors = unique_distractors
        # Compléter avec des stimuli aléatoires de la même catégorie
        remaining = [w for w in available_stimuli if w not in seen]
        while len(selected_distractors) < n-1 and remaining:
            choice = random.choice(remaining)
            selected_distractors.append(choice)
            remaining.remove(choice)
            seen.add(choice)
    
    # Construire la liste finale
    final_choices = [correct_stimulus] + selected_distractors
    random.shuffle(final_choices)
    
    # Vérification critique
    if correct_stimulus not in final_choices:
        final_choices[0] = correct_stimulus
    
    return final_choices[:n]

@app.route('/')
def index():
    """Page d'accueil de l'expérience."""
    return render_template('index.html')

@app.route('/start_experiment', methods=['POST'])
def start_experiment():
    """Démarre une nouvelle session d'expérience."""
    session['session_id'] = str(uuid.uuid4())
    session['participant_id'] = str(uuid.uuid4())  # Génération automatique de l'ID participant
    session['current_block'] = 0
    session['current_trial'] = 0
    session['results'] = []
    
    return jsonify({
        'success': True,
        'session_id': session['session_id'],
        'participant_id': session['participant_id']  # Retourner l'ID généré
    })

@app.route('/get_trial', methods=['POST'])
def get_trial():
    """Génère un nouvel essai pour l'expérience."""
    if 'session_id' not in session:
        return jsonify({'error': 'Session non initialisée'}), 400
    
    data = request.json
    block_type = data.get('block_type', 'bw')  # bw, color, colored_bg
    trial_number = data.get('trial_number', 1)
    
    # Sélectionner un stimulus
    stimulus = random.choice(ALL_STIMULI)
    
    # Déterminer les couleurs selon le bloc
    if block_type == 'colored_bg':
        # Choisir d'abord la couleur de fond
        background_color = random.choice(BACKGROUND_COLORS)
        
        # Choisir une couleur de texte différente du fond
        available_text_colors = list(COLORS.values())
        # Filtrer les couleurs trop similaires au fond
        safe_text_colors = []
        for color in available_text_colors:
            # Vérifier que la couleur n'est pas trop similaire au fond
            if not colors_too_similar(color, background_color):
                safe_text_colors.append(color)
        
        # Si aucune couleur sûre, utiliser noir ou blanc selon le fond
        if not safe_text_colors:
            text_color = "#000000" if is_light_color(background_color) else "#FFFFFF"
        else:
            text_color = random.choice(safe_text_colors)
            
        print(f"🎨 Bloc 3: Fond {background_color} → Texte {text_color}")
        
    elif block_type == 'color':
        text_color = random.choice(list(COLORS.values()))
        background_color = "#FFFFFF"
    else:  # bw
        text_color = "#000000"
        background_color = "#FFFFFF"
    
    # Générer les choix
    with_color = block_type in ['color', 'colored_bg']
    choices = get_choices(stimulus, n=4, with_color_word=with_color)
    
    return jsonify({
        'stimulus': stimulus,
        'text_color': text_color,
        'background_color': background_color,
        'choices': choices,
        'display_time': DISPLAY_TIME,
        'is_word': stimulus in WORDS
    })

@app.route('/submit_trial', methods=['POST'])
def submit_trial():
    """Soumet un essai et retourne le feedback."""
    data = request.json
    
    # Récupérer les données de l'essai
    trial_data = {
        'timestamp': datetime.datetime.now().isoformat(),
        'block_type': data.get('block_type'),
        'trial_number': data.get('trial_number'),
        'stimulus': data.get('stimulus'),
        'response': data.get('response'),
        'correct': data.get('correct'),
        'reaction_time': data.get('reaction_time'),
        'text_color': data.get('text_color'),
        'background_color': data.get('background_color'),
        'is_word': data.get('is_word'),
        'choices': data.get('choices', [])
    }
    
    # Sauvegarder dans le CSV
    save_result(session['session_id'], session.get('participant_id', 'anonymous'), trial_data)
    
    return jsonify({
        'success': True,
        'correct': trial_data['correct']
    })

@app.route('/save_result', methods=['POST'])
def save_result_endpoint():
    """Sauvegarde un résultat envoyé par le client."""
    try:
        data = request.json
        print(f"📥 Réception données: {data}")
        
        # Récupérer les données du résultat
        result_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'participant_id': session.get('participant_id', 'anonymous'),
            'session_id': session.get('session_id', 'unknown'),
            'block_type': data.get('block', 'unknown'),
            'trial_number': data.get('trial', 0),
            'stimulus': data.get('stimulus', ''),
            'response': data.get('response', ''),
            'correct': str(data.get('correct', False)).lower(),
            'reaction_time': data.get('reactionTime', 0),
            'text_color': data.get('textColor', '#000000'),
            'background_color': data.get('backgroundColor', '#ffffff'),
            'is_word': str(data.get('stimulus', '') in WORDS).lower(),
            'choices': data.get('choices', [])
        }
        
        # Sauvegarder dans le CSV
        save_result(session.get('session_id', 'unknown'), session.get('participant_id', 'anonymous'), result_data)
        
        return jsonify({'success': True, 'message': 'Données sauvegardées avec succès'})
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/test_csv')
def test_csv():
    """Route de test pour vérifier la création du CSV."""
    try:
        init_csv()
        
        # Créer un résultat de test
        test_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'trial_number': 1,
            'block_type': 'test',
            'stimulus': 'test_word',
            'response': 'test_response',
            'correct': True,
            'reaction_time': 500,
            'text_color': '#000000',
            'background_color': '#ffffff',
            'is_word': True,
            'choices': ['test_word', 'choice2', 'choice3', 'choice4']
        }
        
        save_result('test_session', 'test_participant', test_data)
        
        return jsonify({
            'success': True, 
            'message': 'Test CSV réussi',
            'file_exists': os.path.exists(RESULTS_FILE),
            'file_path': os.path.abspath(RESULTS_FILE)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin')
@app.route('/admin/')
def admin_login():
    """Page de connexion administrateur."""
    # Si déjà authentifié, rediriger vers le dashboard
    if 'admin_authenticated' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    """Tableau de bord administrateur avec tous les résultats."""
    # Protection basique - vous pouvez améliorer cela
    if request.method == 'POST':
        password = request.form.get('password')
        if password != 'admin123':  # Changez ce mot de passe !
            return render_template('admin_login.html', error='Mot de passe incorrect')
        else:
            session['admin_authenticated'] = True
    elif 'admin_authenticated' not in session:
        return render_template('admin_login.html')
    
    imported = request.args.get('imported')
    skipped = request.args.get('skipped')
    import_error = request.args.get('import_error')
    init_csv()
    if not os.path.exists(RESULTS_FILE):
        return render_template('admin_dashboard.html', results=[], stats={}, imported=imported, skipped=skipped, import_error=import_error)
    
    # Lire tous les résultats avec gestion d'erreur
    results = []
    try:
        with open(RESULTS_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # S'assurer que toutes les clés nécessaires existent
                safe_row = {
                    'participant_id': row.get('participant_id', 'N/A'),
                    'session_id': row.get('session_id', 'N/A'),
                    'timestamp': row.get('timestamp', 'N/A'),
                    'block_type': row.get('block_type', 'unknown'),
                    'trial_number': row.get('trial_number', 'N/A'),
                    'stimulus': row.get('stimulus', 'N/A'),
                    'response': row.get('response', 'N/A'),
                    'correct': row.get('correct', 'false'),
                    'reaction_time': row.get('reaction_time', 'N/A'),
                    'text_color': row.get('text_color', '#000000'),
                    'background_color': row.get('background_color', '#ffffff'),
                    'is_word': row.get('is_word', 'false')
                }
                results.append(safe_row)
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier CSV: {e}")
        return render_template('admin_dashboard.html', results=[], stats={}, error="Erreur lors de la lecture des données")
    
    # Calculer les statistiques par bloc
    stats = calculate_block_statistics(results)
    
    # Grouper les résultats par participant
    participants = {}
    for result in results:
        participant_id = result['participant_id']
        if participant_id not in participants:
            participants[participant_id] = {
                'participant_id': participant_id,
                'session_id': result['session_id'],
                'first_timestamp': result['timestamp'],
                'trials': [],
                'total_trials': 0,
                'correct_trials': 0,
                'avg_reaction_time': 0
            }
        
        participants[participant_id]['trials'].append(result)
        participants[participant_id]['total_trials'] += 1
        if str(result['correct']).lower() == 'true':
            participants[participant_id]['correct_trials'] += 1
    
    # Calculer les statistiques par participant
    for participant_data in participants.values():
        if participant_data['total_trials'] > 0:
            participant_data['accuracy'] = round((participant_data['correct_trials'] / participant_data['total_trials']) * 100, 1)
            
            # Calculer temps de réaction moyen
            reaction_times = []
            for trial in participant_data['trials']:
                try:
                    rt = trial.get('reaction_time', '0')
                    if rt and str(rt).replace('.', '').isdigit():
                        reaction_times.append(float(rt))
                except (ValueError, TypeError):
                    continue
            
            participant_data['avg_reaction_time'] = round(sum(reaction_times) / len(reaction_times), 0) if reaction_times else 0
        else:
            participant_data['accuracy'] = 0
    
    # Convertir en liste et trier par timestamp
    participants_list = list(participants.values())
    participants_list.sort(key=lambda x: x['first_timestamp'])
    
    return render_template('admin_dashboard.html', results=results, stats=stats, participants=participants_list, imported=imported, skipped=skipped, import_error=import_error)

@app.route('/download_results')
def download_results():
    """Télécharge les résultats (accès protégé)."""
    if 'admin_authenticated' not in session:
        return "Accès non autorisé", 403
    
    # S'assurer que le fichier existe
    init_csv()
    
    if os.path.exists(RESULTS_FILE):
        filename = f'experience_results_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return send_file(RESULTS_FILE, as_attachment=True, download_name=filename)
    else:
        return "Aucun résultat disponible", 404

@app.route('/csv_status')
def csv_status():
    """Vérifie le statut du fichier CSV."""
    try:
        init_csv()
        file_exists = os.path.exists(RESULTS_FILE)
        file_size = os.path.getsize(RESULTS_FILE) if file_exists else 0
        
        # Compter les lignes
        line_count = 0
        if file_exists:
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                line_count = sum(1 for line in f) - 1  # -1 pour l'en-tête
        
        return jsonify({
            'file_exists': file_exists,
            'file_path': os.path.abspath(RESULTS_FILE),
            'file_size': file_size,
            'entries_count': max(0, line_count),
            'last_modified': datetime.datetime.fromtimestamp(os.path.getmtime(RESULTS_FILE)).isoformat() if file_exists else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/import_csv', methods=['POST'])
def import_results():
    if 'admin_authenticated' not in session:
        return "Accès non autorisé", 403
    file = request.files.get('file')
    if file is None or file.filename == '':
        return redirect(url_for('admin_dashboard', import_error='Aucun fichier sélectionné'))
    if not file.filename.lower().endswith('.csv'):
        return redirect(url_for('admin_dashboard', import_error='Format non supporté'))
    try:
        init_csv()
        existing_keys = set()
        with open(RESULTS_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (
                    row.get('session_id', ''),
                    row.get('trial_number', ''),
                    row.get('stimulus', ''),
                    row.get('timestamp', ''),
                )
                existing_keys.add(key)
        # Détecter automatiquement le délimiteur (',' ou ';')
        try:
            sample_bytes = file.stream.read(4096)
            sample_text = sample_bytes.decode('utf-8', errors='ignore')
            dialect = csv.Sniffer().sniff(sample_text)
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ','
        finally:
            file.stream.seek(0)

        text_stream = io.TextIOWrapper(file.stream, encoding='utf-8', newline='')
        reader = csv.DictReader(text_stream, delimiter=delimiter)
        header = [
            'session_id', 'participant_id', 'timestamp', 'trial_number', 'block_type',
            'stimulus', 'response', 'correct', 'reaction_time', 'text_color',
            'background_color', 'is_word', 'choices_presented'
        ]
        imported = 0
        skipped = 0
        rows_to_append = []
        for row in reader:
            if 'choices_presented' not in row and 'choices' in row:
                row['choices_presented'] = row.get('choices') or ''
            key = (
                row.get('session_id', ''),
                row.get('trial_number', ''),
                row.get('stimulus', ''),
                row.get('timestamp', ''),
            )
            if key in existing_keys:
                skipped += 1
                continue
            normalized = [row.get(h, '') for h in header]
            rows_to_append.append(normalized)
            existing_keys.add(key)
            imported += 1

        if rows_to_append:
            with RESULTS_LOCK:
                with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows_to_append)
            # Auto-commit après import si des lignes ont été ajoutées
            commit_results_async(f"Import {imported} results from CSV", force_commit=True)
            print(f"📥 Import terminé: {imported} lignes ajoutées, {skipped} doublons ignorés")
        else:
            print(f"📥 Import terminé: aucune nouvelle ligne (tous les {skipped} enregistrements existaient déjà)")

        return redirect(url_for('admin_dashboard', imported=imported, skipped=skipped))
    except Exception as e:
        return redirect(url_for('admin_dashboard', import_error=str(e)))

def calculate_block_statistics(results):
    """Calcule les statistiques par bloc."""
    stats = {}
    
    try:
        # Grouper par bloc
        blocks = {'bw': [], 'color': [], 'colored_bg': []}
        block_names = {'bw': 'Bloc 1: Noir/Blanc', 'color': 'Bloc 2: Couleurs', 'colored_bg': 'Bloc 3: Fonds colorés'}
        
        for result in results:
            block_type = result.get('block_type', '')
            if block_type in blocks:
                blocks[block_type].append(result)
        
        # Calculer les stats pour chaque bloc
        for block_type, block_results in blocks.items():
            if not block_results:
                continue
                
            # Temps de réaction moyen (avec gestion d'erreurs)
            reaction_times = []
            for r in block_results:
                try:
                    rt = r.get('reaction_time', '0')
                    if rt and str(rt).replace('.', '').isdigit():
                        reaction_times.append(float(rt))
                except (ValueError, TypeError):
                    continue
            
            avg_reaction_time = sum(reaction_times) / len(reaction_times) if reaction_times else 0
            
            # Pourcentage de bonnes réponses
            correct_answers = [r for r in block_results if str(r.get('correct', '')).lower() == 'true']
            accuracy = (len(correct_answers) / len(block_results)) * 100 if block_results else 0
            
            # Nombre total d'essais
            total_trials = len(block_results)
            
            stats[block_type] = {
                'name': block_names[block_type],
                'total_trials': total_trials,
                'correct_answers': len(correct_answers),
                'accuracy': round(accuracy, 1),
                'avg_reaction_time': round(avg_reaction_time, 0)
            }
    
    except Exception as e:
        print(f"Erreur dans calculate_block_statistics: {e}")
        # Retourner des stats vides en cas d'erreur
        stats = {}
    
    return stats

if __name__ == '__main__':
    init_csv()
    app.run(debug=True, host='0.0.0.0', port=5000)
