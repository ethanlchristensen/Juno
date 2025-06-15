import os
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import getpass

class FileEncryptor:
    def __init__(self):
        self.key = None
    
    def generate_key_from_password(self, password: str, salt: bytes = None) -> tuple:
        """Generate encryption key from password"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def encrypt_file(self, file_path: str, password: str, output_path: str = None):
        """Encrypt a file with password"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found")
        
        # Generate key and salt
        key, salt = self.generate_key_from_password(password)
        fernet = Fernet(key)
        
        # Read file content
        with open(file_path, 'rb') as file:
            file_data = file.read()
        
        # Encrypt data
        encrypted_data = fernet.encrypt(file_data)
        
        # Prepare output path
        if output_path is None:
            output_path = file_path + '.encrypted'
        
        # Save encrypted file with salt
        with open(output_path, 'wb') as encrypted_file:
            encrypted_file.write(salt + encrypted_data)
        
        print(f"File encrypted successfully: {output_path}")
        return output_path
    
    def decrypt_file(self, encrypted_file_path: str, password: str, output_path: str = None):
        """Decrypt a file with password"""
        if not os.path.exists(encrypted_file_path):
            raise FileNotFoundError(f"Encrypted file {encrypted_file_path} not found")
        
        # Read encrypted file
        with open(encrypted_file_path, 'rb') as encrypted_file:
            file_data = encrypted_file.read()
        
        # Extract salt and encrypted data
        salt = file_data[:16]
        encrypted_data = file_data[16:]
        
        # Generate key from password and salt
        key, _ = self.generate_key_from_password(password, salt)
        fernet = Fernet(key)
        
        try:
            # Decrypt data
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Prepare output path
            if output_path is None:
                output_path = encrypted_file_path.replace('.encrypted', '')
            
            # Save decrypted file
            with open(output_path, 'wb') as decrypted_file:
                decrypted_file.write(decrypted_data)
            
            print(f"File decrypted successfully: {output_path}")
            return output_path
            
        except Exception as e:
            raise ValueError("Invalid password or corrupted file")

def main():
    encryptor = FileEncryptor()
    
    while True:
        print("\n=== File Encryption Tool ===")
        print("1. Encrypt file")
        print("2. Decrypt file")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == '1':
            file_path = input("Enter file path to encrypt: ").strip()
            password = getpass.getpass("Enter password for encryption: ")
            
            try:
                encrypted_path = encryptor.encrypt_file(file_path, password)
                
                # Ask if user wants to delete original
                delete_original = input("Delete original file? (y/N): ").strip().lower()
                if delete_original == 'y':
                    os.remove(file_path)
                    print(f"Original file {file_path} deleted")
                    
            except Exception as e:
                print(f"Error encrypting file: {e}")
        
        elif choice == '2':
            encrypted_path = input("Enter encrypted file path: ").strip()
            password = getpass.getpass("Enter password for decryption: ")
            
            try:
                decrypted_path = encryptor.decrypt_file(encrypted_path, password)
                
            except Exception as e:
                print(f"Error decrypting file: {e}")
        
        elif choice == '3':
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()