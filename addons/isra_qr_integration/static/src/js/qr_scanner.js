// static/src/js/qr_scanner.js
odoo.define('isra_qr_integration.scanner', function (require) {
    'use strict';

    var core = require('web.core');
    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');
    var Dialog = require('web.Dialog');

    publicWidget.registry.QRScanner = publicWidget.Widget.extend({
        selector: '#qr-scanner-container',
        
        events: {
            'click .btn-restart-scanner': '_onRestartScanner',
            'click .btn-switch-camera': '_onSwitchCamera',
            'click .btn-upload-image': '_onUploadImage',
        },
        
        init: function () {
            this._super.apply(this, arguments);
            this.currentStream = null;
            this.scanInterval = null;
            this.isScanning = false;
            this.useFrontCamera = false;
        },
        
        start: function () {
            this._super.apply(this, arguments);
            this.initScanner();
            this._addControls();
        },
        
        destroy: function () {
            this._stopScanning();
            this._super.apply(this, arguments);
        },
        
        _addControls: function () {
            var controlsHtml = `
                <div class="qr-scanner-controls mt-3">
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-primary btn-restart-scanner">
                            <i class="fa fa-refresh"></i> Redémarrer
                        </button>
                        <button type="button" class="btn btn-secondary btn-switch-camera">
                            <i class="fa fa-camera"></i> Changer Caméra
                        </button>
                        <button type="button" class="btn btn-info btn-upload-image">
                            <i class="fa fa-upload"></i> Importer Image
                        </button>
                    </div>
                    <input type="file" id="qr-image-upload" accept="image/*" style="display: none;">
                </div>
            `;
            this.$el.append(controlsHtml);
        },
        
        initScanner: function () {
            var self = this;
            var video = document.getElementById('qr-video');
            
            if (!video) {
                this.showError("Élément vidéo non trouvé");
                return;
            }
            
            // Vérifier la disponibilité de la caméra
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.showError("Caméra non disponible sur cet appareil");
                return;
            }
            
            // Configuration de la caméra
            var constraints = {
                video: {
                    facingMode: this.useFrontCamera ? 'user' : 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            };
            
            this._stopScanning(); // Arrêter le scan précédent si nécessaire
            
            // Demander l'accès à la caméra
            navigator.mediaDevices.getUserMedia(constraints)
                .then(function(stream) {
                    self.currentStream = stream;
                    video.srcObject = stream;
                    video.play();
                    self.startScanning(video);
                    self._hideError();
                })
                .catch(function(err) {
                    console.error("Erreur caméra:", err);
                    if (err.name === 'NotAllowedError') {
                        self.showError("Accès à la caméra refusé. Veuillez autoriser l'accès dans les paramètres de votre navigateur.");
                    } else if (err.name === 'NotFoundError') {
                        self.showError("Aucune caméra trouvée sur cet appareil.");
                    } else {
                        self.showError("Impossible d'accéder à la caméra: " + err.message);
                    }
                });
        },
        
        startScanning: function (video) {
            var self = this;
            var canvas = document.createElement('canvas');
            var context = canvas.getContext('2d');
            
            this.isScanning = true;
            
            // Scanner toutes les 500ms
            this.scanInterval = setInterval(function() {
                if (!self.isScanning) {
                    return;
                }
                
                if (video.readyState === video.HAVE_ENOUGH_DATA) {
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    context.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    var imageData = context.getImageData(0, 0, canvas.width, canvas.height);
                    
                    // Utiliser jsQR pour décoder (nécessite la librairie jsQR)
                    if (window.jsQR) {
                        var code = jsQR(imageData.data, imageData.width, imageData.height);
                        if (code) {
                            self._stopScanning();
                            self.processQRCode(code.data);
                        }
                    } else {
                        // Fallback si jsQR n'est pas disponible
                        self._loadJsQRLibrary().then(function() {
                            // Réessayer après chargement de la librairie
                            if (window.jsQR && self.isScanning) {
                                var code = jsQR(imageData.data, imageData.width, imageData.height);
                                if (code) {
                                    self._stopScanning();
                                    self.processQRCode(code.data);
                                }
                            }
                        });
                    }
                }
            }, 500);
        },
        
        _stopScanning: function () {
            this.isScanning = false;
            
            if (this.scanInterval) {
                clearInterval(this.scanInterval);
                this.scanInterval = null;
            }
            
            if (this.currentStream) {
                this.currentStream.getTracks().forEach(function(track) {
                    track.stop();
                });
                this.currentStream = null;
            }
        },
        
        _loadJsQRLibrary: function () {
            return new Promise(function(resolve, reject) {
                if (window.jsQR) {
                    resolve();
                    return;
                }
                
                var script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js';
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        },
        
        processQRCode: function (qrData) {
            var self = this;
            
            this._showProcessing();
            
            try {
                // Vérifier si c'est un QR code ISRA
                var data;
                if (qrData.startsWith('{')) {
                    // JSON direct
                    data = JSON.parse(qrData);
                } else if (qrData.includes('verification_url') || qrData.includes('lot_id')) {
                    // Données ISRA mais pas en JSON pur
                    data = this._parseISRAData(qrData);
                } else if (qrData.includes('/verify/')) {
                    // URL de vérification
                    var lotId = qrData.split('/verify/')[1];
                    data = { lot_id: lotId };
                } else {
                    throw new Error("Format QR non reconnu");
                }
                
                if (!data.lot_id) {
                    throw new Error("ID de lot manquant dans le QR code");
                }
                
                // Appeler l'API de vérification
                ajax.jsonRpc('/isra/api/verify', 'call', {
                    qr_data: data
                }).then(function (result) {
                    self._hideProcessing();
                    if (result.error) {
                        self.showError(result.error);
                    } else {
                        self.showLotInfo(result.lot, result.authentic);
                    }
                }).catch(function (error) {
                    self._hideProcessing();
                    console.error("Erreur API:", error);
                    self.showError("Erreur de vérification: " + (error.message || "Erreur inconnue"));
                });
                
            } catch (e) {
                this._hideProcessing();
                console.error("Erreur parsing QR:", e);
                this.showError("QR code non reconnu ou invalide: " + e.message);
            }
        },
        
        _parseISRAData: function (qrData) {
            // Méthode pour parser des données ISRA dans différents formats
            var data = {};
            
            // Essayer de parser comme JSON d'abord
            try {
                return JSON.parse(qrData);
            } catch (e) {
                // Pas du JSON, continuer
            }
            
            // Essayer de parser comme paramètres URL
            var lines = qrData.split('\n');
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i].trim();
                if (line.includes(':')) {
                    var parts = line.split(':');
                    var key = parts[0].trim().toLowerCase().replace(/ /g, '_');
                    var value = parts.slice(1).join(':').trim();
                    data[key] = value;
                }
            }
            
            // Mapper les clés vers le format attendu
            if (data.lot_id || data.id_lot || data.id) {
                data.lot_id = data.lot_id || data.id_lot || data.id;
            }
            
            return data;
        },
        
        showLotInfo: function (lot, authentic) {
            var resultDiv = document.getElementById('qr-result');
            var infoDiv = document.getElementById('lot-info');
            
            if (!resultDiv || !infoDiv) {
                this.showError("Éléments d'affichage non trouvés");
                return;
            }
            
            var authenticBadge = authentic ? 
                '<span class="badge badge-success"><i class="fa fa-check"></i> Authentique</span>' :
                '<span class="badge badge-danger"><i class="fa fa-warning"></i> Non Authentique</span>';
            
            var statusBadge = this._getStatusBadge(lot.status);
            var qualityBadge = lot.quality_status ? this._getQualityBadge(lot.quality_status) : '';
            var expiryWarning = lot.days_to_expiry < 30 && lot.days_to_expiry > 0 ? 
                '<div class="alert alert-warning mt-2"><i class="fa fa-clock-o"></i> Expire dans ' + lot.days_to_expiry + ' jours</div>' : '';
            
            if (lot.is_expired) {
                expiryWarning = '<div class="alert alert-danger mt-2"><i class="fa fa-exclamation-triangle"></i> Lot expiré</div>';
            }
            
            infoDiv.innerHTML = `
                <div class="row">
                    <div class="col-md-8">
                        <h5><i class="fa fa-archive"></i> ${lot.name} ${authenticBadge}</h5>
                        <table class="table table-sm table-striped">
                            <tr><td><strong><i class="fa fa-leaf"></i> Variété:</strong></td><td>${lot.variety}</td></tr>
                            <tr><td><strong><i class="fa fa-layer-group"></i> Niveau:</strong></td><td><span class="badge badge-primary">${lot.level}</span></td></tr>
                            <tr><td><strong><i class="fa fa-calendar"></i> Production:</strong></td><td>${lot.production_date}</td></tr>
                            <tr><td><strong><i class="fa fa-info-circle"></i> Statut:</strong></td><td>${statusBadge}</td></tr>
                            ${lot.multiplier ? `<tr><td><strong><i class="fa fa-user"></i> Multiplicateur:</strong></td><td>${lot.multiplier}</td></tr>` : ''}
                            ${qualityBadge ? `<tr><td><strong><i class="fa fa-flask"></i> Qualité:</strong></td><td>${qualityBadge}</td></tr>` : ''}
                        </table>
                        ${expiryWarning}
                    </div>
                    <div class="col-md-4 text-center">
                        <button class="btn btn-primary btn-restart-scanner mb-2">
                            <i class="fa fa-qrcode"></i> Scanner un Autre
                        </button>
                        <br>
                        <button class="btn btn-success" onclick="window.open('/isra/verify/${lot.name}', '_blank')">
                            <i class="fa fa-external-link"></i> Voir Détails
                        </button>
                    </div>
                </div>
            `;
            
            resultDiv.style.display = 'block';
            resultDiv.scrollIntoView({ behavior: 'smooth' });
        },
        
        _getStatusBadge: function (status) {
            var badges = {
                'certified': '<span class="badge badge-success"><i class="fa fa-check"></i> Certifié</span>',
                'pending': '<span class="badge badge-warning"><i class="fa fa-clock-o"></i> En Attente</span>',
                'rejected': '<span class="badge badge-danger"><i class="fa fa-times"></i> Rejeté</span>',
                'in_stock': '<span class="badge badge-info"><i class="fa fa-archive"></i> En Stock</span>',
                'distributed': '<span class="badge badge-secondary"><i class="fa fa-truck"></i> Distribué</span>',
                'draft': '<span class="badge badge-light"><i class="fa fa-pencil"></i> Brouillon</span>',
                'expired': '<span class="badge badge-dark"><i class="fa fa-clock-o"></i> Expiré</span>'
            };
            return badges[status] || `<span class="badge badge-light">${status}</span>`;
        },
        
        _getQualityBadge: function (quality) {
            return quality === 'pass' ? 
                '<span class="badge badge-success"><i class="fa fa-check"></i> Conforme</span>' :
                '<span class="badge badge-danger"><i class="fa fa-times"></i> Non Conforme</span>';
        },
        
        showError: function (message) {
            var resultDiv = document.getElementById('qr-result');
            var infoDiv = document.getElementById('lot-info');
            
            if (!resultDiv || !infoDiv) {
                console.error("Erreur:", message);
                alert("Erreur: " + message);
                return;
            }
            
            infoDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fa fa-exclamation-triangle"></i> Erreur</h5>
                    <p>${message}</p>
                    <button class="btn btn-secondary btn-restart-scanner">
                        <i class="fa fa-refresh"></i> Réessayer
                    </button>
                </div>
            `;
            
            resultDiv.style.display = 'block';
            resultDiv.scrollIntoView({ behavior: 'smooth' });
        },
        
        _hideError: function () {
            var resultDiv = document.getElementById('qr-result');
            if (resultDiv) {
                resultDiv.style.display = 'none';
            }
        },
        
        _showProcessing: function () {
            var resultDiv = document.getElementById('qr-result');
            var infoDiv = document.getElementById('lot-info');
            
            if (resultDiv && infoDiv) {
                infoDiv.innerHTML = `
                    <div class="alert alert-info text-center">
                        <i class="fa fa-spinner fa-spin"></i> Vérification en cours...
                    </div>
                `;
                resultDiv.style.display = 'block';
            }
        },
        
        _hideProcessing: function () {
            // La méthode showLotInfo ou showError remplacera le contenu
        },
        
        // === ÉVÉNEMENTS ===
        
        _onRestartScanner: function () {
            this._hideError();
            this.initScanner();
        },
        
        _onSwitchCamera: function () {
            this.useFrontCamera = !this.useFrontCamera;
            this.initScanner();
        },
        
        _onUploadImage: function () {
            document.getElementById('qr-image-upload').click();
        },
        
        // === SCAN D'IMAGE UPLOADÉE ===
        
        willStart: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Ajouter l'événement pour l'upload d'image
                $(document).on('change', '#qr-image-upload', function (event) {
                    self._processUploadedImage(event);
                });
            });
        },
        
        _processUploadedImage: function (event) {
            var self = this;
            var file = event.target.files[0];
            
            if (!file) {
                return;
            }
            
            if (!file.type.startsWith('image/')) {
                this.showError("Veuillez sélectionner une image valide");
                return;
            }
            
            var reader = new FileReader();
            reader.onload = function (e) {
                var img = new Image();
                img.onload = function () {
                    var canvas = document.createElement('canvas');
                    var context = canvas.getContext('2d');
                    canvas.width = img.width;
                    canvas.height = img.height;
                    context.drawImage(img, 0, 0);
                    
                    var imageData = context.getImageData(0, 0, canvas.width, canvas.height);
                    
                    self._loadJsQRLibrary().then(function () {
                        if (window.jsQR) {
                            var code = jsQR(imageData.data, imageData.width, imageData.height);
                            if (code) {
                                self.processQRCode(code.data);
                            } else {
                                self.showError("Aucun QR code trouvé dans cette image");
                            }
                        } else {
                            self.showError("Impossible de charger la librairie de scan");
                        }
                    });
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
            
            // Reset l'input file
            event.target.value = '';
        }
    });

    // Widget pour les utilisateurs connectés dans le backend Odoo
    var QRScannerBackend = publicWidget.Widget.extend({
        template: 'QRScannerBackend',
        
        init: function (parent, options) {
            this._super.apply(this, arguments);
            this.options = options || {};
        },
        
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Initialiser le scanner une fois le DOM prêt
                self.$el.html(`
                    <div class="qr-scanner-backend">
                        <div class="text-center mb-3">
                            <h4><i class="fa fa-qrcode"></i> Scanner QR Code ISRA</h4>
                        </div>
                        <div id="qr-scanner-container">
                            <video id="qr-video" width="100%" height="400px" autoplay></video>
                            <div id="qr-result" class="mt-3" style="display: none;">
                                <div class="alert alert-success">
                                    <h4>Lot Scanné!</h4>
                                    <div id="lot-info"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `);
                
                // Créer une instance du scanner principal
                var scanner = new publicWidget.registry.QRScanner(self);
                scanner.setElement(self.$('#qr-scanner-container'));
                return scanner.start();
            });
        }
    });

    // Enregistrer les widgets
    publicWidget.registry.QRScannerBackend = QRScannerBackend;

    return {
        QRScanner: publicWidget.registry.QRScanner,
        QRScannerBackend: QRScannerBackend
    };
});