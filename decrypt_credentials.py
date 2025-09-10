#!/usr/bin/env python3
"""
Server-side encryption/decryption utility for user credentials.

This script provides functions to encrypt and decrypt user credentials using
AES-256-GCM encryption with deterministic key derivation from JWT user data.

Usage:
    from decrypt_credentials import CredentialEncryption
    
    # User data from JWT/auth
    user_data = {
        'id': 'user-uuid',
        'email': 'user@example.com', 
        'created_at': '2024-01-01T00:00:00Z',
        'aud': 'authenticated'
    }
    
    # Decrypt credentials
    decrypted = CredentialEncryption.decrypt(encrypted_data, user_data)
    
    # Encrypt new credentials
    encrypted = CredentialEncryption.encrypt("secret_data", user_data)

Requirements:
    pip install cryptography

Security Notes:
    - Keys derived deterministically from user JWT data
    - Same key derivation used on client and server
    - No keys stored - derived on-demand
    - Encryption compatible with TypeScript Web Crypto API implementation
"""

import base64
import json
from typing import Dict, Optional, Any, Union
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import secrets


@dataclass
class UserKeyData:
    """User data for key derivation."""
    id: str
    email: str = ""
    created_at: str = ""
    aud: str = "authenticated"


@dataclass 
class EncryptedData:
    """Encrypted data structure matching TypeScript interface."""
    encrypted_data: str  # Base64 encoded encrypted data
    iv: str             # Base64 encoded initialization vector
    salt: str           # Base64 encoded salt


class CredentialEncryption:
    """Handles encryption/decryption of user credentials with deterministic key derivation."""
    
    ALGORITHM = 'AES-GCM'
    KEY_LENGTH = 32   # 256 bits
    IV_LENGTH = 12    # 96 bits for GCM
    SALT_LENGTH = 16  # 128 bits
    ITERATIONS = 100000  # Same as client-side
    
    @staticmethod
    def _derive_key_from_user_data(user_data: UserKeyData, salt: bytes) -> bytes:
        """Derive encryption key using PBKDF2 from user data."""
        # Create deterministic key material from user data (same as TypeScript)
        key_input = f"{user_data.id}:{user_data.email}:{user_data.created_at}:{user_data.aud}"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=CredentialEncryption.KEY_LENGTH,
            salt=salt,
            iterations=CredentialEncryption.ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(key_input.encode('utf-8'))
    
    @staticmethod
    def encrypt(data: str, user_data: Union[UserKeyData, Dict[str, str]]) -> EncryptedData:
        """
        Encrypt a string using user data for key derivation.
        
        Args:
            data: Plaintext string to encrypt
            user_data: UserKeyData object or dict with user info
            
        Returns:
            EncryptedData object with base64-encoded components
            
        Raises:
            ValueError: If encryption fails
        """
        try:
            # Convert dict to UserKeyData if needed
            if isinstance(user_data, dict):
                user_data = UserKeyData(**user_data)
            
            # Generate random salt and IV
            salt = secrets.token_bytes(CredentialEncryption.SALT_LENGTH)
            iv = secrets.token_bytes(CredentialEncryption.IV_LENGTH)
            
            # Derive key from user data
            key = CredentialEncryption._derive_key_from_user_data(user_data, salt)
            
            # Encrypt using AES-GCM
            aesgcm = AESGCM(key)
            encrypted_bytes = aesgcm.encrypt(iv, data.encode('utf-8'), None)
            
            return EncryptedData(
                encrypted_data=base64.b64encode(encrypted_bytes).decode('utf-8'),
                iv=base64.b64encode(iv).decode('utf-8'),
                salt=base64.b64encode(salt).decode('utf-8')
            )
            
        except Exception as e:
            raise ValueError(f"Encryption failed: {str(e)}")
    
    @staticmethod
    def decrypt(encrypted_data: Union[EncryptedData, Dict[str, str]], user_data: Union[UserKeyData, Dict[str, str]]) -> str:
        """
        Decrypt data using user data for key derivation.
        
        Args:
            encrypted_data: EncryptedData object or dict with encryptedData, iv, salt
            user_data: UserKeyData object or dict with user info
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If decryption fails
        """
        try:
            # Convert dict to objects if needed
            if isinstance(encrypted_data, dict):
                encrypted_data = EncryptedData(
                    encrypted_data=encrypted_data.get('encryptedData', ''),
                    iv=encrypted_data.get('iv', ''),
                    salt=encrypted_data.get('salt', '')
                )
            
            if isinstance(user_data, dict):
                user_data = UserKeyData(**user_data)
            
            # Decode base64 components
            encrypted_bytes = base64.b64decode(encrypted_data.encrypted_data)
            iv = base64.b64decode(encrypted_data.iv)
            salt = base64.b64decode(encrypted_data.salt)
            
            # Derive key from user data
            key = CredentialEncryption._derive_key_from_user_data(user_data, salt)
            
            # Decrypt using AES-GCM
            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(iv, encrypted_bytes, None)
            
            return decrypted_bytes.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    @staticmethod
    def decrypt_user_credentials(settings_row: Dict[str, Any], user_data: Union[UserKeyData, Dict[str, str]]) -> Dict[str, Optional[str]]:
        """
        Decrypt all encrypted fields in a user's settings row.
        
        Args:
            settings_row: Raw settings row from database
            user_data: UserKeyData object or dict with user info
            
        Returns:
            Dictionary with decrypted credential values
        """
        decrypted_credentials = {}
        
        # Convert dict to UserKeyData if needed
        if isinstance(user_data, dict):
            user_data = UserKeyData(**user_data)
        
        # Fields that may be encrypted
        encrypted_fields = [
            'reddit_client_id',
            'reddit_client_secret', 
            'reddit_client_username',
            'reddit_client_password',
            'x_api_key',
            'x_api_secret',
            'twitter_username',
            'twitter_email',
            'twitter_password'
        ]
        
        for field in encrypted_fields:
            if field in settings_row and settings_row[field]:
                field_data = settings_row[field]
                
                # Check if data is encrypted (object) or plain text (string)
                if isinstance(field_data, dict) and all(k in field_data for k in ['encryptedData', 'iv', 'salt']):
                    try:
                        decrypted_credentials[field] = CredentialEncryption.decrypt(field_data, user_data)
                    except ValueError as e:
                        print(f"Warning: Could not decrypt {field}: {e}")
                        decrypted_credentials[field] = None
                elif isinstance(field_data, str):
                    # Plain text data (legacy or unencrypted)
                    decrypted_credentials[field] = field_data
                else:
                    decrypted_credentials[field] = None
        
        return decrypted_credentials


# Convenience functions for common use cases

def decrypt_reddit_credentials(user_settings: Dict[str, Any], user_data: Union[UserKeyData, Dict[str, str]]) -> Dict[str, Optional[str]]:
    """Extract and decrypt Reddit API credentials."""
    credentials = CredentialEncryption.decrypt_user_credentials(user_settings, user_data)
    
    return {
        'client_id': credentials.get('reddit_client_id'),
        'client_secret': credentials.get('reddit_client_secret'),
        'username': credentials.get('reddit_client_username'),
        'password': credentials.get('reddit_client_password')
    }


def decrypt_twitter_credentials(user_settings: Dict[str, Any], user_data: Union[UserKeyData, Dict[str, str]]) -> Dict[str, Optional[str]]:
    """Extract and decrypt Twitter/X API credentials."""
    credentials = CredentialEncryption.decrypt_user_credentials(user_settings, user_data)
    
    return {
        'api_key': credentials.get('x_api_key'),
        'api_secret': credentials.get('x_api_secret')
    }


def get_user_data_from_jwt(jwt_payload: Dict[str, Any]) -> UserKeyData:
    """
    Extract user data from JWT payload for key derivation.
    
    Args:
        jwt_payload: Decoded JWT payload from Supabase auth
        
    Returns:
        UserKeyData object for encryption/decryption
    """
    return UserKeyData(
        id=jwt_payload.get('sub', ''),
        email=jwt_payload.get('email', ''),
        created_at=jwt_payload.get('created_at', ''),
        aud=jwt_payload.get('aud', 'authenticated')
    )


if __name__ == "__main__":
    # Example usage
    print("JWT-Based Credential Encryption Utility")
    print("=" * 45)
    
    # Example user data from JWT
    example_user_data = UserKeyData(
        id="123e4567-e89b-12d3-a456-426614174000",
        email="user@example.com",
        created_at="2024-01-01T00:00:00Z",
        aud="authenticated"
    )
    
    # Example: Encrypt some data
    secret_data = "my_secret_api_key"
    encrypted = CredentialEncryption.encrypt(secret_data, example_user_data)
    
    print(f"Original: {secret_data}")
    print(f"Encrypted: {encrypted.encrypted_data[:20]}...")
    
    # Example: Decrypt the data
    decrypted = CredentialEncryption.decrypt(encrypted, example_user_data)
    print(f"Decrypted: {decrypted}")
    print(f"Match: {secret_data == decrypted}")
    
    print("\nUsage Examples:")
    print("=" * 20)
    
    print("1. Basic encryption/decryption:")
    print("   from decrypt_credentials import CredentialEncryption, UserKeyData")
    print("   user_data = UserKeyData(id='user-id', email='user@example.com', ...)")
    print("   encrypted = CredentialEncryption.encrypt('secret', user_data)")
    print("   decrypted = CredentialEncryption.decrypt(encrypted, user_data)")
    print()
    
    print("2. From JWT payload:")
    print("   user_data = get_user_data_from_jwt(jwt_payload)")
    print("   decrypted = CredentialEncryption.decrypt(encrypted_data, user_data)")
    print()
    
    print("3. Decrypt user credentials:")
    print("   credentials = CredentialEncryption.decrypt_user_credentials(settings_row, user_data)")
    print("   reddit_creds = decrypt_reddit_credentials(settings_row, user_data)")
    print()
    
    print("Security Notes:")
    print("- Keys derived from JWT data (id, email, created_at, aud)")
    print("- Same key derivation used on client and server")
    print("- No keys stored - derived on-demand")
    print("- Compatible with TypeScript Web Crypto API implementation")