from pymongo import ASCENDING, DESCENDING
from bson.objectid import ObjectId
from bson.errors import InvalidId
import re
from datetime import datetime
from flask import current_app
import os


from werkzeug.utils import secure_filename
import uuid



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
# HELPERS
# =================================

def build_field_value(field, form):

    value = form.get(
        field["name"],
        ""
    ).strip()


    if field["type"] == "number":

        try:
            return float(value)

        except ValueError:
            return None


    if field["type"] == "boolean":

        return value in (
            "on",
            "true",
            "1"
        )


    return value



def build_document(fields, form, files, request=None):
    """
    Constrói o documento a partir dos campos da definição do objeto,
    do form enviado e dos arquivos.
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
                from werkzeug.utils import secure_filename
                import uuid
                original_ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{original_ext}"
                # Caminho para salvar
                upload_folder = current_app.config['UPLOAD_FOLDER']
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                # Salva o caminho relativo (ou URL) no banco
                # Exemplo: 'uploads/filename.jpg'
                document[name] = f"uploads/{filename}"
            else:
                # Se não enviou arquivo, mantém o valor existente (para edições)
                # Você pode optar por deixar None ou preservar o antigo
                document[name] = None
        else:
            # Usa a lógica original para outros tipos
            document[name] = build_field_value(field, form)
    return document
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