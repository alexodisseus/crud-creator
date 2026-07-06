from pymongo import ASCENDING, DESCENDING
from bson.objectid import ObjectId
from bson.errors import InvalidId
import re
from datetime import datetime
from flask import current_app
import os
from werkzeug.utils import secure_filename
import uuid
import bcrypt  # Adicione esta importação

db = None

# =================================
# CONEXÃO BANCO
# =================================

def init_db(app):
    global db

    try:
        from pymongo import MongoClient

        client = MongoClient(
            app.config["MONGO_URI"],
            serverSelectionTimeoutMS=3000
        )

        client.admin.command("ping")

        print("[OK] MongoDB conectado")

    except Exception:
        print("[INFO] Usando mongomock")

        import mongomock

        client = mongomock.MongoClient()

    db = client[app.config["DB_NAME"]]

# =================================
# COLLECTIONS
# =================================

OBJ_DEFS_COLLECTION = "_object_definitions"

def get_object_defs_collection():
    return db[OBJ_DEFS_COLLECTION]

def get_data_collection(name):
    return db[name.lower() + "s"]

# =================================
# OBJETOS
# =================================

def get_all_object_definitions():
    return list(
        get_object_defs_collection()
        .find()
        .sort("name", ASCENDING)
    )

def get_object_definition(value):
    collection = get_object_defs_collection()

    try:
        result = collection.find_one(
            {
                "_id": ObjectId(value)
            }
        )

        if result:
            return result

    except (InvalidId, TypeError):
        pass

    return collection.find_one(
        {
            "slug": value
        }
    )

def slugify(text):
    text = text.lower().strip()
    text = re.sub(
        r"[^\w\s-]",
        "",
        text
    )
    text = re.sub(
        r"[\s_-]+",
        "-",
        text
    )
    return text.strip("-")

def ensure_indexes(slug):
    collection = get_data_collection(slug)
    collection.create_index(
        [
            ("created_at", DESCENDING)
        ]
    )

# =================================
# FUNÇÕES DE SEGURANÇA PARA SENHAS
# =================================

def hash_password(password):
    """
    Gera um hash seguro para a senha usando bcrypt.
    
    Args:
        password (str): Senha em texto puro
        
    Returns:
        str: Hash da senha em formato string, ou None se password vazio
    """
    if not password or not password.strip():
        return None
    
    # Gera um salt e faz o hash da senha
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds é um bom equilíbrio segurança/performance
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password, hashed):
    """
    Verifica se a senha corresponde ao hash.
    
    Args:
        password (str): Senha em texto puro para verificar
        hashed (str): Hash armazenado no banco
        
    Returns:
        bool: True se a senha corresponder ao hash, False caso contrário
    """
    if not password or not hashed:
        return False
    
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False

def is_password_field(field):
    """
    Verifica se o campo é do tipo password.
    
    Args:
        field (dict): Definição do campo
        
    Returns:
        bool: True se for campo de senha
    """
    return field.get('type') == 'password'

def should_exclude_from_display(field):
    """
    Verifica se o campo deve ser excluído da exibição (campos sensíveis).
    
    Args:
        field (dict): Definição do campo
        
    Returns:
        bool: True se deve ser excluído
    """
    return field.get('type') in ['password']

# =================================
# HELPERS MODIFICADOS
# =================================

def build_field_value(field, form):
    """
    Constrói o valor de um campo individual.
    Modificado para tratar campos de senha com hashing.
    """
    name = field["name"]
    field_type = field["type"]
    
    # Tratamento especial para campos de senha
    if field_type == "password":
        password = form.get(name, "").strip()
        if password:  # Só faz hash se a senha não estiver vazia
            return hash_password(password)
        return None  # Retorna None para indicar que não deve atualizar
    
    # Para outros campos, mantém o comportamento padrão
    value = form.get(name, "").strip()
    
    if field_type == "number":
        try:
            return float(value)
        except ValueError:
            return None
    
    if field_type == "boolean":
        return value in ("on", "true", "1")
    
    return value

def build_document(fields, form, files, request=None, existing_document=None):
    """
    Constrói o documento a partir dos campos da definição do objeto,
    do form enviado e dos arquivos.
    
    Modificado para:
    - Tratar campos de senha com hashing
    - Preservar senhas existentes quando não fornecidas
    """
    document = {}
    
    for field in fields:
        name = field['name']
        field_type = field['type']
        
        if field_type == 'image':
            # Processa upload de imagem
            file = files.get(name)
            if file and file.filename != '' and allowed_file(file.filename):
                # Gera nome único para evitar conflitos
                original_ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{original_ext}"
                # Caminho para salvar
                upload_folder = current_app.config['UPLOAD_FOLDER']
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                # Salva o caminho relativo (ou URL) no banco
                document[name] = f"uploads/{filename}"
            else:
                # Se não enviou arquivo, mantém o valor existente (para edições)
                if existing_document and name in existing_document:
                    document[name] = existing_document.get(name)
                else:
                    document[name] = None
        
        elif field_type == 'password':
            # Tratamento especial para senha
            password = form.get(name, "").strip()
            
            if password:
                # Se forneceu nova senha, faz o hash
                document[name] = hash_password(password)
            elif existing_document and name in existing_document:
                # Se não forneceu senha e está editando, mantém a existente
                document[name] = existing_document.get(name)
            else:
                # Se não forneceu senha e é criação, deixa None
                document[name] = None
        
        else:
            # Usa a lógica original para outros tipos
            document[name] = build_field_value(field, form)
    
    return document

def get_display_fields(fields):
    """
    Retorna apenas os campos que devem ser exibidos (exclui senhas e outros sensíveis).
    
    Args:
        fields (list): Lista de definições de campos
        
    Returns:
        list: Lista filtrada de campos
    """
    return [f for f in fields if not should_exclude_from_display(f)]

def get_safe_item(item, fields):
    """
    Retorna uma cópia do item com campos sensíveis removidos para exibição.
    
    Args:
        item (dict): Documento do MongoDB
        fields (list): Lista de definições de campos
        
    Returns:
        dict: Cópia do item sem campos sensíveis
    """
    safe_item = item.copy() if item else {}
    
    for field in fields:
        if should_exclude_from_display(field):
            safe_item.pop(field['name'], None)
    
    return safe_item

def get_obj_def_or_404(slug):
    obj = get_object_definition(slug)
    if not obj:
        from flask import abort
        abort(404)
    return obj

def dynamic_url(action, slug, **kwargs):
    from flask import url_for
    return url_for(
        f"main.dynamic_{action}",
        slug=slug,
        **kwargs
    )

def now():
    return datetime.utcnow()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', set())

# =================================
# FUNÇÕES DE VALIDAÇÃO DE SENHA
# =================================

def validate_password_strength(password):
    """
    Valida a força da senha.
    
    Args:
        password (str): Senha a ser validada
        
    Returns:
        tuple: (is_valid, message)
    """
    if not password or len(password) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres"
    
    # Verifica se tem pelo menos uma letra maiúscula
    if not re.search(r'[A-Z]', password):
        return False, "A senha deve conter pelo menos uma letra maiúscula"
    
    # Verifica se tem pelo menos uma letra minúscula
    if not re.search(r'[a-z]', password):
        return False, "A senha deve conter pelo menos uma letra minúscula"
    
    # Verifica se tem pelo menos um número
    if not re.search(r'[0-9]', password):
        return False, "A senha deve conter pelo menos um número"
    
    # Verifica se tem pelo menos um caractere especial
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "A senha deve conter pelo menos um caractere especial"
    
    return True, "Senha válida"

# =================================
# FUNÇÃO PARA BUSCAR POR SENHA (SEGURA)
# =================================

def find_user_by_credentials(collection, email_field, password_field, email, password):
    """
    Busca um usuário por email e verifica a senha de forma segura.
    
    Args:
        collection: Collection do MongoDB
        email_field (str): Nome do campo de email
        password_field (str): Nome do campo de senha
        email (str): Email do usuário
        password (str): Senha em texto puro
        
    Returns:
        dict or None: Usuário se encontrado e senha correta, None caso contrário
    """
    user = collection.find_one({email_field: email})
    
    if user and verify_password(password, user.get(password_field)):
        # Retorna o usuário sem a senha
        user_copy = user.copy()
        user_copy.pop(password_field, None)
        return user_copy
    
    return None