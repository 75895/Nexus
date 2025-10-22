# Sistema de Gestão de Restaurante (Backend Flask + Frontend HTML/Tailwind)

Este é um sistema de gestão de restaurante simplificado, desenvolvido sob medida para atender às necessidades de **controle de estoque**, **ficha técnica** e **baixa automática de insumos** no momento da venda.

A arquitetura é dividida em:
*   **Backend (API):** Desenvolvido em Python com o framework **Flask** e utilizando **SQLite** como banco de dados, o que garante portabilidade e zero configuração.
*   **Frontend (Interface):** Desenvolvido em **HTML, Tailwind CSS e JavaScript Vanilla**, seguindo um design moderno e limpo.

## 1. Pré-requisitos

Para rodar este sistema, você precisará ter instalado em seu computador:

1.  **Python 3** (Recomendado versão 3.8 ou superior)
2.  **VSCode** (ou qualquer editor de código de sua preferência)

## 2. Estrutura de Arquivos

A estrutura de arquivos do projeto é a seguinte:

```
restaurante_system/
├── backend/
│   ├── app.py          # Código principal da API Flask
│   ├── requirements.txt  # Dependências do Python (Flask, flask-cors)
│   └── schema.sql      # Script para criar as tabelas do banco de dados
├── frontend/
│   ├── dashboard.html  # Tela principal de navegação
│   ├── fichas_tecnicas.html # Módulo de Fichas Técnicas
│   ├── insumos.html    # Módulo de Gestão de Insumos/Estoque
│   ├── produtos.html   # Módulo de Gestão de Produtos/Cardápio
│   ├── vendas.html     # Módulo de Registro de Vendas
│   └── index.html      # Tela de Login
└── README.md           # Este arquivo
```

## 3. Configuração e Execução (Passo a Passo)

Siga estes passos para colocar o sistema em funcionamento:

### Passo 3.1: Configurar o Backend

1.  **Abra o VSCode** na pasta `restaurante_system`.
2.  **Instale as dependências do Python:**
    *   Abra o terminal do VSCode (Terminal > New Terminal).
    *   Navegue até a pasta `backend`:
        ```bash
        cd backend
        ```
    *   Instale as bibliotecas necessárias:
        ```bash
        pip install -r requirements.txt
        ```
3.  **Execute o Backend:**
    *   No terminal, ainda na pasta `backend`, execute o arquivo `app.py`:
        ```bash
        python app.py
        ```
    *   Você verá uma mensagem indicando que o banco de dados foi inicializado e o servidor está rodando em `http://127.0.0.1:5000/`.
    *   Deixe este terminal aberto, pois ele mantém o servidor do backend funcionando.

### Passo 3.2: Acessar o Frontend

1.  No VSCode, clique com o botão direito no arquivo `index.html` (localizado dentro da pasta `frontend`).
2.  Selecione a opção **"Open with Live Server"** (se você tiver a extensão Live Server instalada no VSCode) ou simplesmente **"Reveal in File Explorer"** (ou equivalente) e abra o arquivo `index.html` com seu navegador padrão (Chrome, Firefox, etc.).
3.  A tela de login será exibida. Você pode usar qualquer usuário e senha para "entrar" (a autenticação é simplificada para este protótipo, apenas redireciona para o dashboard).

## 4. Fluxo de Uso do Sistema

Para utilizar o sistema e testar a baixa automática de estoque, siga este fluxo:

### 4.1. Cadastrar Insumos (Estoque)

1.  Acesse o módulo **Insumos**.
2.  Cadastre os insumos que você utiliza (ex: "Pão de Hambúrguer", "Carne Moída", "Queijo Cheddar").
3.  Preencha o **Estoque Inicial** (ex: 50 unidades de pão, 10 kg de carne, 5 kg de queijo).
4.  Você pode editar ou excluir insumos existentes.

### 4.2. Cadastrar Produto (Cardápio)

1.  Acesse o módulo **Produtos**.
2.  Cadastre um produto (ex: "Hambúrguer Clássico") e seu preço de venda.
3.  Você pode editar ou excluir produtos existentes.

### 4.3. Criar Ficha Técnica

1.  Acesse o módulo **Fichas Técnicas**.
2.  Selecione o produto (ex: "Hambúrguer Clássico").
3.  Selecione o insumo (ex: "Pão de Hambúrguer") e a **Quantidade Necessária** para 1 unidade do produto (ex: 1).
4.  Repita para todos os insumos do produto (ex: "Carne Moída" - 0.1 kg, "Queijo Cheddar" - 0.05 kg).
5.  Visualize as fichas técnicas cadastradas para cada produto.

### 4.4. Registrar Venda (Baixa Automática)

1.  Acesse o módulo **Vendas**.
2.  Selecione o produto (ex: "Hambúrguer Clássico").
3.  Informe a **Quantidade Vendida** (ex: 5).
4.  Clique em **Registrar Venda**.

O sistema irá:
*   Registrar a venda.
*   Calcular o total de insumos necessários (ex: 5 pães, 0.5 kg de carne, 0.25 kg de queijo).
*   **Automaticamente dar baixa** nesses insumos no seu estoque.

Você pode voltar ao módulo **Insumos** para verificar que o estoque foi atualizado. Se o estoque for insuficiente, o sistema irá bloquear a venda e emitir um alerta.

---
**Desenvolvido por Manus AI**
**Tecnologias:** Python (Flask), SQLite, HTML, Tailwind CSS, JavaScript.
