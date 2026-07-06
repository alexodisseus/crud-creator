from flask import Blueprint, jsonify, request
from bson.objectid import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from model import *

api_bp = Blueprint("api", __name__, url_prefix='/api')

@api_bp.route('/<slug>')
def api_index(slug):
    """
    GET /api/<slug>
    Lista todos os registros com suporte a paginação e busca.
    
    Query params:
    - page: número da página (default: 1)
    - per_page: registros por página (default: 20)
    - q: termo de busca
    - sort: campo para ordenação (default: created_at)
    - order: asc ou desc (default: desc)
    - fields: campos específicos separados por vírgula (ex: titulo,autor)
    """
    obj_def = get_obj_def_or_404(slug)
    collection = get_data_collection(slug)
    
    # Parâmetros de paginação
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)  # Limita a 100 registros por página
    
    # Parâmetro de busca
    search = request.args.get('q', '')
    
    # Parâmetros de ordenação
    sort_field = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    # Campos específicos (projeção)
    fields_param = request.args.get('fields', '')
    
    # Constrói a query
    query = {}
    if search:
        or_conditions = []
        for field in obj_def.get('fields', []):
            if field['type'] in ('text', 'textarea', 'email', 'url'):
                or_conditions.append({
                    field['name']: {'$regex': search, '$options': 'i'}
                })
        if or_conditions:
            query['$or'] = or_conditions
    
    # Constrói a projeção
    projection = None
    if fields_param:
        fields_list = [f.strip() for f in fields_param.split(',')]
        projection = {field: 1 for field in fields_list}
        projection['_id'] = 1  # Sempre inclui o _id
    
    # Constrói a ordenação
    sort_direction = DESCENDING if sort_order.lower() == 'desc' else ASCENDING
    
    # Executa a query
    cursor = collection.find(query, projection)
    cursor = cursor.sort(sort_field, sort_direction)
    
    # Conta total de registros
    total = collection.count_documents(query)
    
    # Paginação
    skip = (page - 1) * per_page
    cursor = cursor.skip(skip).limit(per_page)
    
    # Converte para lista
    items = list(cursor)
    
    # Prepara resposta
    response = {
        'success': True,
        'data': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 0,
            'has_next': (page * per_page) < total,
            'has_prev': page > 1
        }
    }
    
    return jsonify(response)


@api_bp.route('/<slug>/<item_id>')
def api_show(slug, item_id):
    """
    GET /api/<slug>/<item_id>
    Retorna um registro específico.
    """
    obj_def = get_obj_def_or_404(slug)
    
    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({
            'success': False,
            'error': 'ID inválido',
            'message': f'O ID fornecido ({item_id}) não é um ObjectId válido.'
        }), 400
    
    item = get_data_collection(slug).find_one({'_id': oid})
    
    if not item:
        return jsonify({
            'success': False,
            'error': 'Registro não encontrado',
            'message': f'{obj_def["name"]} com ID {item_id} não encontrado.'
        }), 404
    
    return jsonify({
        'success': True,
        'data': item
    })


@api_bp.route('/<slug>', methods=['POST'])
def api_create(slug):
    """
    POST /api/<slug>
    Cria um novo registro.
    
    Body: JSON com os dados do registro
    """
    obj_def = get_obj_def_or_404(slug)
    
    # Verifica se o Content-Type é JSON
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Content-Type inválido',
            'message': 'A requisição deve ter Content-Type: application/json'
        }), 400
    
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Dados inválidos',
            'message': 'O corpo da requisição está vazio ou não é um JSON válido.'
        }), 400
    
    # Adiciona timestamps
    data['created_at'] = datetime.utcnow()
    data['updated_at'] = data['created_at']
    
    # Insere no banco
    result = get_data_collection(slug).insert_one(data)
    
    # Busca o registro inserido
    new_item = get_data_collection(slug).find_one({'_id': result.inserted_id})
    
    return jsonify({
        'success': True,
        'message': f'{obj_def["name"]} criado com sucesso!',
        'data': new_item
    }), 201


@api_bp.route('/<slug>/<item_id>', methods=['PUT', 'PATCH'])
def api_update(slug, item_id):
    """
    PUT/PATCH /api/<slug>/<item_id>
    Atualiza um registro existente.
    """
    obj_def = get_obj_def_or_404(slug)
    
    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({
            'success': False,
            'error': 'ID inválido',
            'message': f'O ID fornecido ({item_id}) não é um ObjectId válido.'
        }), 400
    
    # Verifica se o registro existe
    existing = get_data_collection(slug).find_one({'_id': oid})
    if not existing:
        return jsonify({
            'success': False,
            'error': 'Registro não encontrado',
            'message': f'{obj_def["name"]} com ID {item_id} não encontrado.'
        }), 404
    
    # Verifica se o Content-Type é JSON
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Content-Type inválido',
            'message': 'A requisição deve ter Content-Type: application/json'
        }), 400
    
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Dados inválidos',
            'message': 'O corpo da requisição está vazio ou não é um JSON válido.'
        }), 400
    
    # Remove campos que não devem ser atualizados diretamente
    data.pop('_id', None)
    data.pop('created_at', None)
    
    # Atualiza timestamp
    data['updated_at'] = datetime.utcnow()
    
    # Atualiza no banco
    get_data_collection(slug).update_one(
        {'_id': oid},
        {'$set': data}
    )
    
    # Busca o registro atualizado
    updated_item = get_data_collection(slug).find_one({'_id': oid})
    
    return jsonify({
        'success': True,
        'message': f'{obj_def["name"]} atualizado com sucesso!',
        'data': updated_item
    })


@api_bp.route('/<slug>/<item_id>', methods=['DELETE'])
def api_delete(slug, item_id):
    """
    DELETE /api/<slug>/<item_id>
    Remove um registro.
    """
    obj_def = get_obj_def_or_404(slug)
    
    try:
        oid = ObjectId(item_id)
    except InvalidId:
        return jsonify({
            'success': False,
            'error': 'ID inválido',
            'message': f'O ID fornecido ({item_id}) não é um ObjectId válido.'
        }), 400
    
    # Verifica se o registro existe
    existing = get_data_collection(slug).find_one({'_id': oid})
    if not existing:
        return jsonify({
            'success': False,
            'error': 'Registro não encontrado',
            'message': f'{obj_def["name"]} com ID {item_id} não encontrado.'
        }), 404
    
    # Remove o registro
    get_data_collection(slug).delete_one({'_id': oid})
    
    return jsonify({
        'success': True,
        'message': f'{obj_def["name"]} removido com sucesso!'
    })


@api_bp.route('/<slug>/batch', methods=['POST'])
def api_batch_delete(slug):
    """
    POST /api/<slug>/batch
    Operações em lote (ex: deletar múltiplos registros).
    
    Body: 
    {
        "action": "delete",
        "ids": ["id1", "id2", ...]
    }
    """
    obj_def = get_obj_def_or_404(slug)
    
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Content-Type inválido',
            'message': 'A requisição deve ter Content-Type: application/json'
        }), 400
    
    data = request.get_json()
    action = data.get('action')
    
    if action == 'delete':
        ids = data.get('ids', [])
        if not ids:
            return jsonify({
                'success': False,
                'error': 'IDs não fornecidos',
                'message': 'Forneça uma lista de IDs para deletar.'
            }), 400
        
        # Converte strings para ObjectId
        try:
            object_ids = [ObjectId(id_str) for id_str in ids]
        except InvalidId as e:
            return jsonify({
                'success': False,
                'error': 'IDs inválidos',
                'message': f'Um ou mais IDs são inválidos: {str(e)}'
            }), 400
        
        # Deleta os registros
        result = get_data_collection(slug).delete_many({'_id': {'$in': object_ids}})
        
        return jsonify({
            'success': True,
            'message': f'{result.deleted_count} registro(s) removido(s) com sucesso!',
            'deleted_count': result.deleted_count
        })
    
    return jsonify({
        'success': False,
        'error': 'Ação não suportada',
        'message': f'Ação "{action}" não é suportada. Use "delete".'
    }), 400