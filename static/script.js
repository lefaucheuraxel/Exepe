class ExperimentApp {
    constructor() {
        this.currentScreen = 'welcome-screen';
        this.currentBlock = 0;
        this.currentTrial = 0;
        this.totalTrials = 10;
        this.totalBlocks = 3;
        this.blockTypes = ['bw', 'color', 'colored_bg'];
        this.blockTitles = [
            'Bloc 1: Stimuli en noir',
            'Bloc 2: Stimuli en couleur', 
            'Bloc 3: Stimuli colorés sur fonds colorés'
        ];
        this.blockDescriptions = [
            "Une croix va apparaître, puis un mot va s'afficher très brièvement. Vous devrez le reconnaître parmi les choix proposés.",
            "Une croix va apparaître, puis un mot va s'afficher très brièvement. Vous devrez le reconnaître parmi les choix proposés.",
            "Une croix va apparaître, puis un mot va s'afficher très brièvement. Vous devrez le reconnaître parmi les choix proposés."
        ];
        
        this.currentTrialData = null;
        this.trialStartTime = null;
        this.results = [];
        this.currentBackgroundColor = '#ffffff';
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.showScreen('welcome-screen');
    }
    
    bindEvents() {
        // Bouton démarrer
        document.getElementById('start-btn').addEventListener('click', () => {
            this.startExperiment();
        });
        
        // Bouton démarrer bloc
        document.getElementById('start-block-btn').addEventListener('click', () => {
            this.startBlock();
        });
        
        // Boutons de choix
        document.querySelectorAll('.choice-btn').forEach((btn, index) => {
            btn.addEventListener('click', () => {
                this.selectChoice(index);
            });
        });
        
        // Bouton continuer (pause)
        document.getElementById('continue-btn').addEventListener('click', () => {
            this.nextBlock();
        });
        
        // Bouton envoyer les résultats
        document.getElementById('send-results-btn').addEventListener('click', () => {
            this.sendFinalResults();
        });
        
        // Touches clavier pour les choix
        document.addEventListener('keydown', (e) => {
            if (this.currentScreen === 'choice-screen') {
                const key = e.key;
                if (['1', '2', '3', '4'].includes(key)) {
                    this.selectChoice(parseInt(key) - 1);
                }
            }
        });
    }
    
    showScreen(screenId) {
        // Cacher tous les écrans
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        
        // Afficher l'écran demandé
        document.getElementById(screenId).classList.add('active');
        this.currentScreen = screenId;
        
        // S'assurer que le fond reste blanc pour tous les écrans sauf pendant l'affichage du stimulus
        if (screenId !== 'trial-screen') {
            document.body.style.backgroundColor = '#ffffff';
            document.body.classList.remove('colored-background');
        }
    }
    
    async startExperiment() {
        this.showScreen('loading-screen');
        
        try {
            const response = await fetch('/start_experiment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                this.participantId = data.participant_id;
                
                // Afficher l'ID généré automatiquement
                document.getElementById('participant-id-display').textContent = this.participantId;
                
                this.currentBlock = 0;
                this.currentTrial = 0;
                this.results = [];
                this.showBlockInstructions();
            } else {
                alert('Erreur lors du démarrage de l\'expérience');
                this.showScreen('welcome-screen');
            }
        } catch (error) {
            console.error('Erreur:', error);
            alert('Erreur de connexion');
            this.showScreen('welcome-screen');
        }
    }
    
    showBlockInstructions() {
        document.getElementById('block-title').textContent = this.blockTitles[this.currentBlock];
        document.getElementById('block-description').innerHTML = this.blockDescriptions[this.currentBlock];
        this.showScreen('block-instructions');
    }
    
    async startBlock() {
        this.currentTrial = 0;
        this.nextTrial();
    }
    
    async nextTrial() {
        if (this.currentTrial >= this.totalTrials) {
            // Bloc terminé
            if (this.currentBlock < this.totalBlocks - 1) {
                this.showPause();
            } else {
                this.showResults();
            }
            return;
        }
        
        this.currentTrial++;
        
        // Afficher info de l'essai
        document.getElementById('trial-counter').textContent = 
            `Essai ${this.currentTrial}/${this.totalTrials}`;
        
        // Garder le container transparent au début de l'essai
        // Il ne redeviendra visible qu'au moment des choix
        const trialContainer = document.querySelector('#trial-screen .container');
        if (trialContainer) {
            trialContainer.style.backgroundColor = 'transparent';
            trialContainer.style.boxShadow = 'none';
            trialContainer.style.border = 'none';
        }
        
        this.showScreen('trial-screen');
        
        // Attendre 1.5 secondes puis afficher croix
        setTimeout(() => {
            this.showFixationCross();
        }, 1500);
    }
    
    showFixationCross() {
        document.getElementById('trial-info').style.display = 'none';
        document.getElementById('fixation-cross').style.display = 'block';
        
        // Rendre le container transparent pendant la croix de fixation
        const container = document.querySelector('#trial-screen .container');
        if (container) {
            container.style.backgroundColor = 'transparent';
            container.style.boxShadow = 'none';
            container.style.border = 'none';
        }
        
        console.log('🎯 Croix affichée - Container transparent');
        
        // Afficher croix pendant 1 seconde puis stimulus
        setTimeout(() => {
            this.showStimulus();
        }, 1000);
    }
    
    async showStimulus() {
        try {
            const response = await fetch('/get_trial', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    block_type: this.blockTypes[this.currentBlock],
                    trial_number: this.currentTrial
                })
            });
            
            const trialData = await response.json();
            this.currentTrialData = trialData;
            
            // Cacher la croix
            document.getElementById('fixation-cross').style.display = 'none';
            
            // Changer la couleur de fond AVANT d'afficher le stimulus
            if (trialData.background_color !== '#FFFFFF') {
                this.currentBackgroundColor = trialData.background_color;
                document.body.style.setProperty('--bg-color', trialData.background_color);
                document.body.classList.add('colored-background');
                document.body.style.backgroundColor = trialData.background_color;
                
                // Pour le bloc 3, rendre le container de la même couleur que le fond
                const container = document.querySelector('#trial-screen .container');
                if (container) {
                    container.style.backgroundColor = trialData.background_color;
                }
                
                console.log('Fond coloré appliqué:', trialData.background_color);
            } else {
                this.currentBackgroundColor = '#ffffff';
                document.body.classList.remove('colored-background');
                document.body.style.backgroundColor = '#ffffff';
                
                // Container transparent pour les blocs 1 et 2
                const container = document.querySelector('#trial-screen .container');
                if (container) {
                    container.style.backgroundColor = 'transparent';
                }
            }
            
            // Configurer l'affichage du stimulus
            const stimulusEl = document.getElementById('stimulus-display');
            stimulusEl.textContent = trialData.stimulus;
            stimulusEl.style.color = trialData.text_color;
            stimulusEl.classList.add('visible');
            
            // Afficher pendant le temps spécifié
            setTimeout(() => {
                this.hideStimulus();
            }, trialData.display_time);
            
        } catch (error) {
            console.error('Erreur lors de la récupération de l\'essai:', error);
        }
    }
    
    hideStimulus() {
        // Cacher le stimulus
        const stimulusEl = document.getElementById('stimulus-display');
        stimulusEl.classList.remove('visible');
        
        // TOUJOURS remettre le fond blanc après l'affichage du stimulus
        // Même pour le bloc 3, le fond coloré ne doit être visible que pendant les 50ms du stimulus
        document.body.style.backgroundColor = '#ffffff';
        document.body.classList.remove('colored-background');
        document.body.style.removeProperty('--bg-color');
        this.currentBackgroundColor = '#ffffff';
        
        console.log('🔄 Fond remis en blanc après stimulus');
        
        // Le container reste transparent ici, il sera restauré dans showChoices()
        
        // Afficher les choix
        this.showChoices();
    }
    
    showChoices() {
        // Restaurer l'apparence normale du container SEULEMENT au moment des choix
        const trialContainer = document.querySelector('#trial-screen .container');
        if (trialContainer) {
            trialContainer.style.backgroundColor = '#ffffff';
            trialContainer.style.boxShadow = '0 4px 20px rgba(0,0,0,0.1)';
            trialContainer.style.border = '';
        }
        
        console.log('📋 Container restauré pour les choix');
        
        // Configurer les boutons de choix
        const choices = this.currentTrialData.choices;
        const colors = ['#FF0000', '#00C800', '#0000FF', '#8B00FF', '#FF6600', '#FF00FF']; // Rouge, Vert, Bleu, Violet, Orange, Magenta
        
        document.querySelectorAll('.choice-btn').forEach((btn, index) => {
            btn.textContent = `${index + 1}. ${choices[index]}`;
            
            // Réinitialiser les styles
            btn.style.color = '';
            btn.style.backgroundColor = '';
            btn.style.border = '';
            
            // Ajouter des couleurs aux réponses dans les blocs 2 et 3 pour induire en erreur
            if (this.blockTypes[this.currentBlock] === 'color' || this.blockTypes[this.currentBlock] === 'colored_bg') {
                // Choisir une couleur aléatoire différente pour chaque bouton
                const randomColor = colors[index % colors.length];
                btn.style.color = randomColor;
                btn.style.fontWeight = 'bold';
                btn.classList.add('colored');
                
                // Pour le bloc 3, ajouter aussi une bordure colorée
                if (this.blockTypes[this.currentBlock] === 'colored_bg') {
                    btn.style.border = `3px solid ${randomColor}`;
                    btn.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                }
            } else {
                btn.classList.remove('colored');
            }
        });
        
        // Le fond reste blanc pour tous les blocs pendant les choix
        // Le fond coloré du bloc 3 n'est visible que pendant l'affichage du stimulus (50ms)
        document.body.style.backgroundColor = '#ffffff';
        document.body.classList.remove('colored-background');
        
        // Enregistrer le temps de début pour mesurer le temps de réaction
        this.trialStartTime = Date.now();
        
        this.showScreen('choice-screen');
    }
    
    async selectChoice(choiceIndex) {
        const reactionTime = Date.now() - this.trialStartTime;
        const selectedChoice = this.currentTrialData.choices[choiceIndex];
        const isCorrect = selectedChoice === this.currentTrialData.stimulus;
        
        // Envoyer la réponse au serveur
        try {
            await fetch('/submit_trial', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    trial_number: this.currentTrial,
                    block_type: this.blockTypes[this.currentBlock],
                    stimulus: this.currentTrialData.stimulus,
                    response: selectedChoice,
                    correct: isCorrect,
                    reaction_time: reactionTime,
                    text_color: this.currentTrialData.text_color,
                    background_color: this.currentTrialData.background_color,
                    is_word: this.currentTrialData.is_word,
                    choices: this.currentTrialData.choices
                })
            });
        } catch (error) {
            console.error('Erreur lors de l\'envoi de la réponse:', error);
        }
        
        // Sauvegarder localement aussi avec toutes les données
        this.results.push({
            trial: this.currentTrial,
            block: this.currentBlock,
            stimulus: this.currentTrialData.stimulus,
            response: selectedChoice,
            correct: isCorrect,
            reactionTime: reactionTime,
            textColor: this.currentTrialData.text_color,
            backgroundColor: this.currentTrialData.background_color,
            choices: this.currentTrialData.choices,
            isWord: this.currentTrialData.is_word
        });
        
        // Rendre le container transparent immédiatement après la sélection
        const trialContainer = document.querySelector('#trial-screen .container');
        if (trialContainer) {
            trialContainer.style.backgroundColor = 'transparent';
            trialContainer.style.boxShadow = 'none';
            trialContainer.style.border = 'none';
        }
        
        console.log('🔄 Container rendu transparent après sélection');
        
        // Passer au prochain essai après un court délai (sans feedback)
        setTimeout(() => {
            this.nextTrial();
        }, 500); // Délai de 500ms pour éviter que ce soit trop rapide
    }
    
    showFeedback(isCorrect, correctAnswer, userAnswer) {
        const messageEl = document.getElementById('feedback-message');
        const detailsEl = document.getElementById('feedback-details');
        
        // Pour le bloc 3, remettre temporairement le fond blanc pour le feedback
        if (this.blockTypes[this.currentBlock] === 'colored_bg') {
            document.body.style.backgroundColor = '#ffffff';
        }
        
        if (isCorrect) {
            messageEl.textContent = 'Correct !';
            messageEl.className = 'correct';
            detailsEl.textContent = '';
        } else {
            messageEl.textContent = 'Incorrect';
            messageEl.className = 'incorrect';
            detailsEl.textContent = `Le stimulus était : ${correctAnswer}`;
        }
        
        this.showScreen('feedback-screen');
        
        // Continuer après 1 seconde
        setTimeout(() => {
            this.nextTrial();
        }, 1000);
    }
    
    showPause() {
        const pauseTitles = [
            'Fin du Bloc 1',
            'Fin du Bloc 2'
        ];
        
        const pauseMessages = [
            'Prenez une petite pause si nécessaire.<br>Le prochain bloc utilisera des stimuli en couleur sur fond blanc.<br><br>Prêt pour le Bloc 2 ?',
            'Prenez une petite pause si nécessaire.<br>Le dernier bloc sera plus difficile:<br>stimuli colorés sur des fonds colorés !<br><br>Prêt pour le Bloc 3 ?'
        ];
        
        document.getElementById('pause-title').textContent = pauseTitles[this.currentBlock];
        document.getElementById('pause-message').innerHTML = pauseMessages[this.currentBlock];
        
        this.showScreen('pause-screen');
    }
    
    nextBlock() {
        // Remettre le fond blanc entre les blocs
        document.body.style.backgroundColor = '#ffffff';
        document.body.classList.remove('colored-background');
        document.body.style.removeProperty('--bg-color');
        this.currentBackgroundColor = '#ffffff';
        this.currentBlock++;
        this.showBlockInstructions();
    }
    
    showResults() {
        // Remettre le fond blanc pour l'affichage des résultats
        document.body.style.backgroundColor = '#ffffff';
        document.body.classList.remove('colored-background');
        document.body.style.removeProperty('--bg-color');
        this.currentBackgroundColor = '#ffffff';
        
        // Calculer les statistiques
        const totalCorrect = this.results.filter(r => r.correct).length;
        const totalTrials = this.results.length;
        const accuracy = ((totalCorrect / totalTrials) * 100).toFixed(1);
        
        const avgReactionTime = (this.results.reduce((sum, r) => sum + r.reactionTime, 0) / totalTrials).toFixed(0);
        
        // Statistiques par bloc
        const blockStats = [];
        for (let i = 0; i < 3; i++) {
            const blockResults = this.results.filter(r => r.block === i);
            const blockCorrect = blockResults.filter(r => r.correct).length;
            const blockAccuracy = ((blockCorrect / blockResults.length) * 100).toFixed(1);
            blockStats.push({
                name: this.blockTitles[i],
                correct: blockCorrect,
                total: blockResults.length,
                accuracy: blockAccuracy
            });
        }
        
        // Afficher les résultats
        const resultsHTML = `
            <h3>Résultats Globaux</h3>
            <p><strong>Précision totale:</strong> ${totalCorrect}/${totalTrials} (${accuracy}%)</p>
            <p><strong>Temps de réaction moyen:</strong> ${avgReactionTime}ms</p>
            <br>
            <h3>Résultats par Bloc</h3>
            ${blockStats.map(block => 
                `<p><strong>${block.name}:</strong> ${block.correct}/${block.total} correct (${block.accuracy}%)</p>`
            ).join('')}
            <br>
            <h3>Analyse</h3>
            <p>Effet de la couleur: ${(blockStats[1].accuracy - blockStats[0].accuracy).toFixed(1)}%</p>
            <p>Effet du fond coloré: ${(blockStats[2].accuracy - blockStats[1].accuracy).toFixed(1)}%</p>
            <p>Difficulté totale: ${(blockStats[2].accuracy - blockStats[0].accuracy).toFixed(1)}%</p>
        `;
        
        document.getElementById('results-content').innerHTML = resultsHTML;
        this.showScreen('results-screen');
    }
    
    restart() {
        this.currentBlock = 0;
        this.currentTrial = 0;
        this.results = [];
        this.currentTrialData = null;
        this.trialStartTime = null;
        this.currentBackgroundColor = '#ffffff';
        
        // Réinitialiser l'affichage
        document.getElementById('trial-info').style.display = 'block';
        document.getElementById('fixation-cross').style.display = 'none';
        document.getElementById('stimulus-display').classList.remove('visible');
        document.body.style.backgroundColor = '#ffffff';
        document.body.classList.remove('colored-background');
        document.body.style.removeProperty('--bg-color');
        
        // Restaurer l'apparence normale de tous les containers
        document.querySelectorAll('.container').forEach(container => {
            container.style.backgroundColor = '#ffffff';
            container.style.boxShadow = '0 4px 20px rgba(0,0,0,0.1)';
            container.style.border = '';
        });
        
        this.showScreen('welcome-screen');
    }
    
    async sendFinalResults() {
        try {
            // Afficher un message de confirmation
            const confirmSend = confirm('Êtes-vous sûr de vouloir envoyer vos résultats ? Cette action est définitive.');
            if (!confirmSend) {
                return;
            }
            
            // Changer le texte du bouton
            const btn = document.getElementById('send-results-btn');
            btn.textContent = '📤 Envoi en cours...';
            btn.disabled = true;
            
            // Activer la barre de progression
            const progressWrap = document.getElementById('send-progress');
            const progressBar = document.getElementById('send-progress-bar');
            const progressText = document.getElementById('send-progress-text');
            if (progressWrap && progressBar && progressText) {
                progressWrap.style.display = 'flex';
                progressBar.style.width = '0%';
                progressText.textContent = '0%';
            }
            
            console.log('📤 Envoi des résultats:', this.results);
            
            // Envoyer tous les résultats stockés localement avec plus de détails
            let successCount = 0;
            const total = this.results.length || 0;
            if (total === 0) {
                if (progressBar && progressText) {
                    progressBar.style.width = '100%';
                    progressText.textContent = '100%';
                }
            }
            for (let i = 0; i < total; i++) {
                const result = this.results[i];
                try {
                    const response = await fetch('/save_result', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            trial: result.trial,
                            block: this.blockTypes[result.block],
                            stimulus: result.stimulus,
                            response: result.response,
                            correct: result.correct,
                            reactionTime: result.reactionTime,
                            textColor: result.textColor || '#000000',
                            backgroundColor: result.backgroundColor || '#ffffff',
                            choices: result.choices || []
                        })
                    });
                    
                    const responseData = await response.json();
                    if (responseData.success) {
                        successCount++;
                        console.log(`✅ Résultat ${successCount} envoyé avec succès`);
                    } else {
                        console.error('❌ Erreur serveur:', responseData.error);
                    }
                } catch (error) {
                    console.error('❌ Erreur réseau:', error);
                }
                // Mettre à jour la progression
                if (progressBar && progressText && total > 0) {
                    const percent = Math.round(((i + 1) / total) * 100);
                    progressBar.style.width = `${percent}%`;
                    progressText.textContent = `${percent}%`;
                }
            }
            
            // Succès
            btn.textContent = `✅ ${successCount}/${this.results.length} résultats envoyés !`;
            btn.style.backgroundColor = '#27ae60';
            
            // Afficher un message de confirmation
            setTimeout(() => {
                alert(`Vos résultats ont été envoyés avec succès ! (${successCount}/${this.results.length} réussites)\nMerci pour votre participation.`);
            }, 500);
            
        } catch (error) {
            console.error('Erreur lors de l\'envoi des résultats:', error);
            const btn = document.getElementById('send-results-btn');
            btn.textContent = '❌ Erreur d\'envoi';
            btn.style.backgroundColor = '#e74c3c';
            btn.disabled = false;
            
            alert('Erreur lors de l\'envoi des résultats. Veuillez réessayer.');
        }
    }
}

// Initialiser l'application quand la page est chargée
document.addEventListener('DOMContentLoaded', () => {
    new ExperimentApp();
});
