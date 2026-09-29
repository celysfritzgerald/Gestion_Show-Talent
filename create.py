import os

def create_upload_folders():
    """Créer la structure des dossiers uploads"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    uploads_path = os.path.join(base_path, 'uploads')
    
    folders = ['artists', 'moments', 'sponsors', 'lyrics']
    
    print("=" * 50)
    print("📁 CRÉATION DES DOSSIERS UPLOADS")
    print("=" * 50)
    
    # Créer le dossier principal
    os.makedirs(uploads_path, exist_ok=True)
    print(f"✅ {uploads_path}")
    
    for folder in folders:
        path = os.path.join(uploads_path, folder)
        os.makedirs(path, exist_ok=True)
        
        # Créer .gitkeep
        gitkeep = os.path.join(path, '.gitkeep')
        if not os.path.exists(gitkeep):
            with open(gitkeep, 'w') as f:
                f.write(f'# Dossier pour les {folder}\n')
        print(f"✅ {path}")
    
    print("=" * 50)
    print("✅ Structure créée avec succès!")

if __name__ == '__main__':
    create_upload_folders()