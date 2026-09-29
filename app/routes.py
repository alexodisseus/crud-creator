from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from bson.objectid import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from model import *
from utils.security import hash_password, should_exclude_from_display

main_bp = Blueprint(
    "main",
    __name__
)

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def build_document(fields, form_data, files_data, existing_item=None):
    """
    Constrói o documento a ser salvo no MongoDB.
    Modificado para tratar campos de senha com hashing.
    """
    data = {}
    
    for field in fields:
        field_name = field['name']
        field_type = field.get('type', 'text')
        
        # Tratamento especial para campos de senha
        if field_type == 'password':
            password = form_data.get(field_name, '').strip()
            if password:  # Só faz hash se a senha não estiver vazia
                data[field_name] = hash_password(password)
            elif existing_item and field_name in existing_item:
                # Se não forneceu senha e está editando, mantém a existente
                data[field_name] = existing_item.get(field_name)
            else:
                data[field_name] = None
        else:
            # Para outros campos, mantém o comportamento padrão
            value = form_data.get(field_name, '')
            
            # Tratamento especial para campos de imagem
            if field_type == 'image' and field_name in files_data:
                file = files_data[field_name]
                if file and file.filename:
                    # Salva a imagem (lógica existente)
                    data[field_name] = save_image(file)
                elif existing_item and field_name in existing_item:
                    data[field_name] = existing_item.get(field_name)
                else:
                    data[field_name] = value
            else:
                data[field_name] = value
    
    return data

def get_display_fields(fields):
    """Retorna apenas os campos que devem ser exibidos (exclui senhas)."""
    return [f for f in fields if not should_exclude_from_display(f)]

def get_safe_item(item, fields):
    """
    Retorna uma cópia do item com campos sensíveis removidos para exibição.
    """
    if not item:
        return {}
    
    safe_item = item.copy()
    for field in fields:
        if should_exclude_from_display(field):
            safe_item.pop(field['name'], None)
    return safe_item

def save_image(file):
    """Salva uma imagem e retorna o caminho."""
    from werkzeug.utils import secure_filename
    import os
    import uuid
    
    if not file or not file.filename:
        return None
    
    original_ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{original_ext}"
    
    from flask import current_app
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    
    return f"uploads/{filename}"

# ============================================================================
# ROTAS ADMIN
# ============================================================================

@main_bp.route('/admin')
def admin_dashboard():
    """Painel principal do administrador."""
    objects = get_all_object_definitions()
    stats = []
    for obj in objects:
        count = get_data_collection(obj['slug']).count_documents({})
        stats.append({
            'definition': obj,
            'count': count
        })
    return render_template('admin/dashboard.html', stats=stats)



@main_bp.route('/admin/objetos')
def admin_listar_objetos():
    """Lista todos os tipos de objetos cadastrados."""
    objects = get_all_object_definitions()
    return render_template('admin/listar_objetos.html', objects=objects)

@main_bp.route('/admin/objetos/criar', methods=['GET', 'POST'])
def admin_criar_objeto():
    """Cria um novo tipo de objeto (ex: Livro)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        plural_name = request.form.get('plural_name', '').strip()
        description = request.form.get('description', '').strip()
        fields_raw = request.form.get('fields', '').strip()

        if not name:
            flash('O nome do objeto é obrigatório.', 'error')
            return redirect(url_for('main.admin_criar_objeto'))

        slug = slugify(name)

        # Verifica se já existe
        existing = get_object_definition(slug)
        if existing:
            flash(f'Já existe um objeto com o nome "{name}".', 'error')
            return redirect(url_for('main.admin_criar_objeto'))

        # Parse dos campos
        fields = []
        if fields_raw:
            for line in fields_raw.split('\n'):
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(':')]
                field_name = slugify(parts[0]).replace('-', '_')
                field_type = parts[1].lower() if len(parts) > 1 else 'text'
                field_label = parts[2] if len(parts) > 2 else parts[0]

                valid_types = ['text', 'number', 'date', 'textarea', 'select', 'boolean', 'email', 'url', 'password', 'image']
                if field_type not in valid_types:
                    field_type = 'text'

                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'label': field_label
                })

        obj_def = {
            'name': name,
            'slug': slug,
            'plural_name': plural_name or name + 's',
            'description': description,
            'fields': fields,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        get_object_defs_collection().insert_one(obj_def)
        ensure_indexes(slug)

        flash(f'Objeto "{name}" criado com sucesso! Rotas disponíveis em /{slug}/', 'success')
        return redirect(url_for('main.admin_listar_objetos'))

    return render_template('admin/criar_objeto.html')

@main_bp.route('/admin/objetos/editar/<obj_id>', methods=['GET', 'POST'])
def admin_editar_objeto(obj_id):
    """Edita um tipo de objeto existente."""
    obj_def = get_object_definition(obj_id)
    if not obj_def:
        flash('Objeto não encontrado.', 'error')
        return redirect(url_for('main.admin_listar_objetos'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        plural_name = request.form.get('plural_name', '').strip()
        description = request.form.get('description', '').strip()
        fields_raw = request.form.get('fields', '').strip()

        if not name:
            flash('O nome do objeto é obrigatório.', 'error')
            return redirect(url_for('main.admin_editar_objeto', obj_id=obj_id))

        # Parse dos campos
        fields = []
        if fields_raw:
            for line in fields_raw.split('\n'):
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(':')]
                field_name = slugify(parts[0]).replace('-', '_')
                field_type = parts[1].lower() if len(parts) > 1 else 'text'
                field_label = parts[2] if len(parts) > 2 else parts[0]

                valid_types = ['text', 'number', 'date', 'textarea', 'select', 'boolean', 'email', 'url', 'password', 'image']
                if field_type not in valid_types:
                    field_type = 'text'

                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'label': field_label
                })

        get_object_defs_collection().update_one(
            {'_id': obj_def['_id']},
            {'$set': {
                'name': name,
                'plural_name': plural_name or name + 's',
                'description': description,
                'fields': fields,
                'updated_at': datetime.utcnow()
            }}
        )

        flash(f'Objeto "{name}" atualizado com sucesso!', 'success')
        return redirect(url_for('main.admin_listar_objetos'))

    # Formata campos para exibição no textarea
    fields_text = '\n'.join([
        f"{f['name']}:{f['type']}:{f['label']}"
        for f in obj_def.get('fields', [])
    ])

    return render_template('admin/editar_objeto.html', obj=obj_def, fields_text=fields_text)

@main_bp.route('/admin/objetos/deletar/<obj_id>', methods=['POST'])
def admin_deletar_objeto(obj_id):
    """Remove um tipo de objeto e todos os seus dados."""
    obj_def = get_object_definition(obj_id)
    if not obj_def:
        flash('Objeto não encontrado.', 'error')
        return redirect(url_for('main.admin_listar_objetos'))

    # Remove a collection de dados
    get_data_collection(obj_def['slug']).drop()
    # Remove a definição
    get_object_defs_collection().delete_one({'_id': obj_def['_id']})

    flash(f'Objeto "{obj_def["name"]}" e todos os seus dados foram removidos.', 'success')
    return redirect(url_for('main.admin_listar_objetos'))

# ============================================================================
# ROTAS CRUD DINÂMICAS GENÉRICAS (APENAS UMA VEZ)
# ============================================================================

@main_bp.route('/<slug>/index')
def dynamic_index(slug):
    """Lista todos os registros de um tipo de objeto."""
    obj_def = get_obj_def_or_404(slug)
    collection = get_data_collection(slug)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search = request.args.get('q', '')

    query = {}
    if search:
        or_conditions = []
        # Não busca em campos de senha
        for field in obj_def.get('fields', []):
            if field['type'] in ('text', 'textarea', 'email', 'url'):
                or_conditions.append({
                    field['name']: {'$regex': search, '$options': 'i'}
                })
        if or_conditions:
            query['$or'] = or_conditions

    total = collection.count_documents(query)
    items = list(collection.find(query)
                 .sort('created_at', DESCENDING)
                 .skip((page - 1) * per_page)
                 .limit(per_page))

    # Remove campos de senha dos itens para exibição
    safe_items = []
    for item in items:
        safe_item = get_safe_item(item, obj_def.get('fields', []))
        safe_items.append(safe_item)

    total_pages = (total + per_page - 1) // per_page

    return render_template('crud/index.html',
                           obj_def=obj_def,
                           items=safe_items,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           search=search)

@main_bp.route('/<slug>/ver/<item_id>')
def dynamic_ver(slug, item_id):
    """Exibe os detalhes de um registro."""
    obj_def = get_obj_def_or_404(slug)
    try:
        oid = ObjectId(item_id)
    except InvalidId:
        flash('ID inválido.', 'error')
        return redirect(dynamic_url('index', slug))

    item = get_data_collection(slug).find_one({'_id': oid})
    if not item:
        flash(f'{obj_def["name"]} não encontrado.', 'error')
        return redirect(dynamic_url('index', slug))

    # Remove campos de senha para exibição
    safe_item = get_safe_item(item, obj_def.get('fields', []))
    display_fields = get_display_fields(obj_def.get('fields', []))

    return render_template('crud/ver.html', 
                           obj_def=obj_def, 
                           item=safe_item,
                           display_fields=display_fields)

@main_bp.route('/<slug>/criar', methods=['GET', 'POST'])
def dynamic_criar(slug):
    """Cria um novo registro."""
    obj_def = get_obj_def_or_404(slug)
    display_fields = get_display_fields(obj_def.get('fields', []))

    if request.method == 'POST':
        # Constrói o documento com tratamento de senhas
        data = build_document(
            obj_def.get('fields', []), 
            request.form, 
            request.files,
            existing_item=None
        )

        data['created_at'] = datetime.utcnow()
        data['updated_at'] = data['created_at']

        result = get_data_collection(slug).insert_one(data)
        flash(f'{obj_def["name"]} criado com sucesso!', 'success')
        return redirect(dynamic_url('ver', slug, item_id=str(result.inserted_id)))

    return render_template('crud/form.html', 
                          obj_def=obj_def, 
                          item=None,
                          display_fields=display_fields)

@main_bp.route('/<slug>/editar/<item_id>', methods=['GET', 'POST'])
def dynamic_editar(slug, item_id):
    """Edita um registro existente."""
    obj_def = get_obj_def_or_404(slug)
    display_fields = get_display_fields(obj_def.get('fields', []))
    
    try:
        oid = ObjectId(item_id)
    except InvalidId:
        flash('ID inválido.', 'error')
        return redirect(dynamic_url('index', slug))

    collection = get_data_collection(slug)
    item = collection.find_one({'_id': oid})
    if not item:
        flash(f'{obj_def["name"]} não encontrado.', 'error')
        return redirect(dynamic_url('index', slug))

    if request.method == 'POST':
        # Constrói o documento considerando campos especiais e preservando existentes
        data = build_document(
            obj_def.get('fields', []), 
            request.form, 
            request.files,
            existing_item=item
        )

        data['updated_at'] = datetime.utcnow()
        collection.update_one({'_id': oid}, {'$set': data})

        flash(f'{obj_def["name"]} atualizado com sucesso!', 'success')
        return redirect(dynamic_url('ver', slug, item_id=item_id))

    safe_item = get_safe_item(item, obj_def.get('fields', []))

    return render_template(
        'crud/form.html',
        obj_def=obj_def,
        item=safe_item,
        display_fields=display_fields
    )

@main_bp.route('/<slug>/deletar/<item_id>', methods=['GET', 'POST'])
def dynamic_deletar(slug, item_id):
    """Exclui um registro."""
    obj_def = get_obj_def_or_404(slug)
    try:
        oid = ObjectId(item_id)
    except InvalidId:
        flash('ID inválido.', 'error')
        return redirect(dynamic_url('index', slug))

    collection = get_data_collection(slug)
    item = collection.find_one({'_id': oid})
    if not item:
        flash(f'{obj_def["name"]} não encontrado.', 'error')
        return redirect(dynamic_url('index', slug))

    if request.method == 'POST':
        collection.delete_one({'_id': oid})
        flash(f'{obj_def["name"]} removido com sucesso!', 'success')
        return redirect(dynamic_url('index', slug))

    # Remove campos de senha para exibição
    safe_item = get_safe_item(item, obj_def.get('fields', []))

    return render_template('crud/confirmar_delete.html', 
                          obj_def=obj_def, 
                          item=safe_item)

# ============================================================================
# ROTA HOME
# ============================================================================

@main_bp.route('/')
def home():
    """Página inicial redireciona para o admin."""
    return redirect(url_for('cadastro_ecc.home'))

# ============================================================================
# CONTEXTO GLOBAL PARA TEMPLATES
# ============================================================================

@main_bp.context_processor
def inject_globals():
    """Injeta variáveis globais em todos os templates."""
    return {
        'object_definitions': get_all_object_definitions(),
        'dynamic_url': dynamic_url,
        'get_display_fields': get_display_fields,
        'get_safe_item': get_safe_item
    }




ecc_bp = Blueprint(
    "cadastro_ecc",
    __name__,
    url_prefix='/cadastro_ecc'
)
@ecc_bp.route('/asd')
def home():
    
    return "asd asd asd"
