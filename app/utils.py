import os
import uuid
import imghdr
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image
import re

def allowed_file(filename):
    """Vérifier si l'extension du fichier est autorisée"""
    if not filename or '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in current_app.config['ALLOWED_EXTENSIONS']

def get_file_extension(filename):
    """Récupérer l'extension du fichier"""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()

def validate_image_content(filepath):
    """Valider le contenu d'une image"""
    try:
        # Vérifier que c'est bien une image avec imghdr
        image_type = imghdr.what(filepath)
        if not image_type:
            return False
        
        # Ouvrir avec PIL pour validation supplémentaire
        with Image.open(filepath) as img:
            # Vérifier les dimensions
            width, height = img.size
            max_width, max_height = current_app.config.get('MAX_IMAGE_DIMENSIONS', (4096, 4096))
            if width > max_width or height > max_height:
                return False
            
            # Vérifier le mode et convertir si nécessaire
            if img.mode in ('RGBA', 'LA'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1])
                rgb_img.save(filepath, 'JPEG', quality=85)
            elif img.mode != 'RGB':
                img.convert('RGB').save(filepath, 'JPEG', quality=85)
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Erreur validation image: {str(e)}")
        return False

def save_uploaded_file(file, subfolder):
    """
    Sauvegarder un fichier uploadé avec validation de sécurité
    Retourne le nom du fichier ou lève une exception
    """
    if not file or not file.filename:
        return None
    
    # ✅ Vérifier l'extension
    extension = get_file_extension(file.filename)
    if not allowed_file(file.filename):
        raise ValueError(f"Type de fichier non autorisé. Formats acceptés: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}")
    
    # ✅ Vérifier le MIME type
    if file.mimetype not in current_app.config['ALLOWED_MIME_TYPES']:
        raise ValueError(f"Type MIME non autorisé. Types acceptés: {', '.join(current_app.config['ALLOWED_MIME_TYPES'])}")
    
    # ✅ Vérifier la taille
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = current_app.config['MAX_CONTENT_LENGTH']
    if file_size > max_size:
        raise ValueError(f"Fichier trop volumineux. Taille maximale: {max_size // (1024*1024)}MB")
    
    # ✅ Générer un nom de fichier sécurisé avec UUID
    filename = f"{uuid.uuid4().hex}.{extension}"
    
    # ✅ Chemin de sauvegarde avec chemin absolu
    upload_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_path, exist_ok=True)
    
    filepath = os.path.join(upload_path, filename)
    
    # ✅ Sauvegarder
    try:
        file.save(filepath)
        current_app.logger.info(f"✅ Fichier sauvegardé: {filepath}")
        
        # ✅ Valider le contenu
        if not validate_image_content(filepath):
            os.remove(filepath)
            raise ValueError("Fichier image invalide ou corrompu")
        
        # ✅ Permissions sécurisées
        try:
            os.chmod(filepath, 0o644)
        except:
            pass
        
        return filename
        
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        current_app.logger.error(f"Erreur sauvegarde fichier: {str(e)}")
        raise ValueError(f"Erreur lors de la sauvegarde: {str(e)}")

def delete_uploaded_file(filename, subfolder):
    """Supprimer un fichier uploadé"""
    if not filename:
        return
    
    filepath = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], subfolder, filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            current_app.logger.info(f"✅ Fichier supprimé: {filepath}")
    except Exception as e:
        current_app.logger.error(f"Erreur suppression fichier {filename}: {str(e)}")

def get_file_url(filename, subfolder):
    """Obtenir l'URL d'un fichier uploadé"""
    if not filename:
        return None
    return f"/uploads/{subfolder}/{filename}"

def get_file_path(filename, subfolder):
    """Obtenir le chemin absolu d'un fichier uploadé"""
    if not filename:
        return None
    return os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], subfolder, filename)