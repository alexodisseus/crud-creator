# utils/security.py
import bcrypt

def hash_password(password):
    """Gera um hash seguro para a senha usando bcrypt."""
    if not password or not password.strip():
        return None
    
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password, hashed):
    """Verifica se a senha corresponde ao hash."""
    if not password or not hashed:
        return False
    
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False

def should_exclude_from_display(field):
    """Verifica se o campo deve ser excluído da exibição."""
    return field.get('type') == 'password'