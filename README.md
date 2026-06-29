# Dynamic CRUD Generator

Sistema em **Flask + PyMongo** que permite criar objetos dinamicamente e gera automaticamente todas as telas de CRUD (Criar, Listar, Visualizar, Editar, Deletar).

## Funcionalidades

- **Painel Administrativo** (`/admin`) para gerenciar tipos de objetos
- **CRUD Auto-gerado** ao criar um objeto, todas as rotas e telas sao criadas automaticamente
- **MongoDB** como banco de dados (com fallback para mongomock em memoria)
- **Busca** em tempo real nos registros
- **Paginacao** de resultados
- **Tipos de campos suportados**: text, textarea, number, date, email, url, boolean, select

## Como Usar

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar MongoDB (opcional)

Por padrao, o sistema tenta conectar ao MongoDB em `localhost:27017`. Se nao estiver disponivel, usa `mongomock` (MongoDB em memoria).

Para usar MongoDB real, configure a variavel de ambiente:
```bash
export MONGO_URI="mongodb://localhost:27017/"
export DB_NAME="dynamic_crud_db"
```

### 3. Iniciar o servidor

```bash
python app.py
```

Acesse: http://localhost:5000

## Exemplo de Uso

### Criar objeto "Livro"

1. Acesse `/admin/objetos/criar`
2. Preencha:
   - **Nome**: Livro
   - **Plural**: Livros
   - **Descricao**: Livros da biblioteca
   - **Campos**:
     ```
     titulo:text:Titulo
     autor:text:Autor
     genero:text:Genero
     preco:number:Preco
     publicacao:date:Data de Publicacao
     ```
3. Clique em "Criar Objeto"

### Rotas geradas automaticamente

| Acao | Rota | Descricao |
|------|------|-----------|
| Listar | `/livro/index` | Lista todos os livros |
| Ver | `/livro/ver/<id>` | Visualiza um livro |
| Criar | `/livro/criar` | Formulario de criacao |
| Editar | `/livro/editar/<id>` | Formulario de edicao |
| Deletar | `/livro/deletar/<id>` | Confirmacao de exclusao |

## Tipos de Campos

| Tipo | Descricao |
|------|-----------|
| `text` | Texto curto (input) |
| `textarea` | Texto longo (area de texto) |
| `number` | Numero inteiro ou decimal |
| `date` | Data (seletor de data) |
| `email` | E-mail com validacao |
| `url` | URL com link clicavel |
| `boolean` | Checkbox Sim/Nao |
| `select` | Dropdown de selecao |
| `password` | Campo de senha |

## Formato dos Campos

No formulario de criacao/edicao de objetos, um campo por linha:
```
nome_campo:tipo:Rotulo Visivel
```

Exemplos:
```
nome:text:Nome Completo
preco:number:Preco Unitario
descricao:textarea:Descricao Detalhada
data_nascimento:date:Data de Nascimento
email:email:E-mail de Contato
site:url:Website
ativo:boolean:Ativo
```

## Estrutura do Projeto

```
app/
├── app.py                  # Aplicacao Flask principal
├── config.py               # Configuracoes
├── requirements.txt        # Dependencias Python
├── README.md               # Este arquivo
├── static/
│   └── css/
│       └── style.css       # Estilos CSS
└── templates/
    ├── base.html           # Template base
    ├── admin/
    │   ├── dashboard.html      # Painel principal
    │   ├── listar_objetos.html # Listar tipos de objetos
    │   ├── criar_objeto.html   # Criar novo tipo
    │   └── editar_objeto.html  # Editar tipo
    └── crud/
        ├── index.html          # Listagem de registros
        ├── ver.html            # Visualizar registro
        ├── form.html           # Form criar/editar
        └── confirmar_delete.html # Confirmar exclusao
```

## Tecnologias

- **Flask** - Framework web
- **PyMongo** - Driver MongoDB para Python
- **mongomock** - MongoDB em memoria (fallback)
- **MongoDB** - Banco de dados NoSQL
