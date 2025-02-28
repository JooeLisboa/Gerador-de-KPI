import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# Inicializar authenticator como None
authenticator = None

# Carregar credenciais do arquivo YAML com tratamento detalhado de erros e depuração
try:
    import os
    print(f"Checando arquivo credentials.yaml em: {os.path.abspath('credentials.yaml')}")
    if not os.path.exists('credentials.yaml'):
        st.error("Arquivo credentials.yaml não encontrado. Crie o arquivo com credenciais válidas no diretório atual.")
        st.stop()

    with open('credentials.yaml', 'r', encoding='utf-8') as file:
        config = yaml.load(file, Loader=SafeLoader)
    print("Configuração carregada:", config)  # Depuração para verificar o conteúdo

    if not config or 'credentials' not in config or 'usernames' not in config['credentials']:
        st.error("O arquivo credentials.yaml está vazio, mal formatado, ou não contém a chave 'usernames'. Verifique a estrutura.")
        st.stop()

    # Adicionar depuração para verificar os usernames antes de criar o authenticator
    config['credentials']
    print("Usuários carregados:")

    authenticator = stauth.Authenticate(
    config['credentials'],  # Pass the entire 'credentials' dictionary
    cookie_name=config['cookie']['name'],
    cookie_key=config['cookie']['key'],
    cookie_expiry_days=config['cookie']['expiry_days']
)
    print("Authenticator criado com sucesso:", authenticator)
except FileNotFoundError:
    st.error("Arquivo credentials.yaml não encontrado. Crie o arquivo com credenciais válidas no diretório atual.")
    st.stop()
except yaml.YAMLError as e:
    st.error(f"Erro de sintaxe no arquivo credentials.yaml: {e}")
    st.stop()
except KeyError as e:
    st.error(f"Chave ausente no credentials.yaml: {e}. Verifique a estrutura do arquivo (ex.: 'usernames' deve estar dentro de 'credentials').")
    st.stop()
except Exception as e:
    st.error(f"Erro inesperado ao carregar credenciais: {e}")
    st.stop()

# Verificar se authenticator foi criado antes de usar
if authenticator is None:
    st.error("Falha na inicialização do autenticador. Verifique o arquivo credentials.yaml, as dependências e a estrutura.")
    st.stop()

# Verificar autenticação
name, authentication_status, = authenticator.login("Login", "main")

if authentication_status == False:
    st.error("Usuário/Senha incorretos")
elif authentication_status == None:
    st.warning("Por favor, insira seu usuário e senha")
elif authentication_status:
    st.write(f"Bem-vindo, {name}!")
    authenticator.logout("Logout", "sidebar")
    
    # ... (o resto do código, incluindo funções processar_dados, calcular_kpis, criar_graficos, etc., permanece o mesmo)
    # Função para carregar e processar o arquivo Excel
    def processar_dados(arquivo):
        try:
            dados = pd.read_excel(arquivo)
            if dados.empty:
                st.error("O arquivo Excel está vazio.")
                return None
            # Validação de colunas esperadas
            colunas_esperadas = ["Product_ID", "Sale_Date", "Sales_Rep_Region", "Sales_Amount", "Quantity_Sold", "Product_Category", "Unit_Cost", "Unit_Price", "Customer_Type", "Discount", "Payment_Method", "Sales_Channel", "Region_and_Sales_Rep"]
            colunas_faltantes = [col for col in colunas_esperadas if col not in dados.columns]
            if colunas_faltantes:
                st.warning(f"Colunas ausentes: {colunas_faltantes}. Algumas funcionalidades podem não estar disponíveis.")
            # Validação de dados
            if "Sale_Date" in dados.columns:
                dados["Sale_Date"] = pd.to_datetime(dados["Sale_Date"], errors="coerce")
                if dados["Sale_Date"].isna().all():
                    st.error("Datas inválidas no arquivo Excel.")
                    return None
            if "Sales_Amount" in dados.columns and (dados["Sales_Amount"] < 0).any():
                st.error("Valores negativos em Sales_Amount encontrados. Verifique os dados.")
                return None
            return dados
        except Exception as e:
            st.error(f"Erro ao carregar o arquivo: {e}")
            return None

    # Função para calcular KPIs
    def calcular_kpis(dados):
        if dados is None or dados.empty:
            return {}
        
        kpis = {}
        colunas = dados.columns.tolist()
        tipos = dados.dtypes.to_dict()

        def eh_numerico(col): return np.issubdtype(tipos[col], np.number)
        def eh_data(col): return "date" in col.lower() or pd.api.types.is_datetime64_any_dtype(dados[col])

        for coluna in colunas:
            if eh_numerico(coluna) and not dados[coluna].isna().all():
                kpis[f"Total {coluna}"] = dados[coluna].sum()
                kpis[f"Média {coluna}"] = dados[coluna].mean()
                kpis[f"Máximo {coluna}"] = dados[coluna].max()
                kpis[f"Mínimo {coluna}"] = dados[coluna].min()

        if eh_data("Sale_Date") and not dados["Sale_Date"].isna().all():
            kpis["Período Analisado"] = f"{dados['Sale_Date'].min().strftime('%d/%m/%Y')} a {dados['Sale_Date'].max().strftime('%d/%m/%Y')}"
            kpis["Dias Totais"] = (dados["Sale_Date"].max() - dados["Sale_Date"].min()).days + 1

        if "Sales_Amount" in colunas and "Unit_Cost" in colunas and not dados[["Sales_Amount", "Unit_Cost", "Quantity_Sold"]].isna().all().any():
            kpis["Receita Total"] = dados["Sales_Amount"].sum() if not dados["Sales_Amount"].isna().all() else 0
            kpis["Custo Total"] = (dados["Unit_Cost"].sum() * dados["Quantity_Sold"].sum()) if not dados[["Unit_Cost", "Quantity_Sold"]].isna().all().any() else 0
            if kpis["Receita Total"] > 0:
                kpis["Margem de Lucro (%)"] = ((kpis["Receita Total"] - kpis["Custo Total"]) / kpis["Receita Total"]) * 100

        if "Sales_Amount" in colunas and "Product_Category" in colunas and not dados[["Sales_Amount", "Product_Category"]].isna().all().any():
            kpis["Vendas por Categoria"] = dados.groupby("Product_Category")["Sales_Amount"].sum().dropna().to_dict()
            kpis["Lucro por Categoria"] = (dados.groupby("Product_Category")["Sales_Amount"].sum() - dados.groupby("Product_Category")["Unit_Cost"].sum() * dados.groupby("Product_Category")["Quantity_Sold"].sum()).dropna().to_dict()

        if "Sales_Amount" in colunas and "Sales_Channel" in colunas and not dados[["Sales_Amount", "Sales_Channel"]].isna().all().any():
            kpis["Vendas por Canal"] = dados.groupby("Sales_Channel")["Sales_Amount"].sum().dropna().to_dict()
            kpis["Lucro por Canal"] = (dados.groupby("Sales_Channel")["Sales_Amount"].sum() - dados.groupby("Sales_Channel")["Unit_Cost"].sum() * dados.groupby("Sales_Channel")["Quantity_Sold"].sum()).dropna().to_dict()

        if "Sales_Amount" in colunas and "Region_and_Sales_Rep" in colunas and not dados[["Sales_Amount", "Region_and_Sales_Rep"]].isna().all().any():
            kpis["Vendas por Região/Representante"] = dados.groupby("Region_and_Sales_Rep")["Sales_Amount"].sum().dropna().to_dict()
            kpis["Lucro por Região/Representante"] = (dados.groupby("Region_and_Sales_Rep")["Sales_Amount"].sum() - dados.groupby("Region_and_Sales_Rep")["Unit_Cost"].sum() * dados.groupby("Region_and_Sales_Rep")["Quantity_Sold"].sum()).dropna().to_dict()

        if "Sales_Amount" in colunas and "Sale_Date" in colunas:
            dados["Sale_Date"] = pd.to_datetime(dados["Sale_Date"], errors="coerce")
            vendas_mensais = dados.groupby(dados["Sale_Date"].dt.to_period('M'))["Sales_Amount"].sum().dropna()
            if not vendas_mensais.empty:
                kpis["Crescimento de Vendas Mensal (%)"] = ((vendas_mensais / vendas_mensais.shift(1) - 1) * 100).dropna().to_dict()

        if "Customer_Type" in colunas and "Sales_Amount" in colunas:
            kpis["Ticket Médio por Tipo de Cliente"] = dados.groupby("Customer_Type")["Sales_Amount"].mean().dropna().to_dict()

        return kpis

    # Função para criar gráficos
    def criar_graficos(dados):
        if dados is None or dados.empty:
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle("Relatórios Visuais de KPIs", fontsize=16)

        ax1, ax2, ax3, ax4 = axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]

        # Gráfico 1: Vendas por Categoria (Gráfico de Barras)
        if "Product_Category" in dados.columns and "Sales_Amount" in dados.columns:
            vendas_categoria = dados.groupby("Product_Category")["Sales_Amount"].sum().dropna()
            if not vendas_categoria.empty:
                sns.barplot(x=vendas_categoria.index, y=vendas_categoria.values, ax=ax1, palette="Blues_d")
                ax1.set_title("Vendas por Categoria")
                ax1.set_xlabel("Categoria")
                ax1.set_ylabel("Valor (R$)")
                ax1.tick_params(axis='x', rotation=45)
            else:
                ax1.text(0.5, 0.5, "Sem dados disponíveis", ha='center', va='center')

        # Gráfico 2: Vendas por Canal (Gráfico de Pizza)
        if "Sales_Channel" in dados.columns and "Sales_Amount" in dados.columns:
            vendas_canal = dados.groupby("Sales_Channel")["Sales_Amount"].sum().dropna()
            if not vendas_canal.empty:
                vendas_canal.plot(kind="pie", ax=ax2, autopct='%1.1f%%', colors=['#FF6B6B', '#4ECDC4', '#45B7D1'])
                ax2.set_title("Vendas por Canal")
            else:
                ax2.text(0.5, 0.5, "Sem dados disponíveis", ha='center', va='center')

        # Gráfico 3: Vendas por Região/Representante (Gráfico de Linhas)
        if "Region_and_Sales_Rep" in dados.columns and "Sales_Amount" in dados.columns:
            vendas_regiao = dados.groupby("Region_and_Sales_Rep")["Sales_Amount"].sum().dropna()
            if not vendas_regiao.empty:
                vendas_regiao.plot(kind="line", ax=ax3, marker='o', color='#FFA500', linewidth=2)
                ax3.set_title("Vendas por Região/Representante")
                ax3.set_xlabel("Região/Representante")
                ax3.set_ylabel("Valor (R$)")
                ax3.tick_params(axis='x', rotation=45)
            else:
                ax3.text(0.5, 0.5, "Sem dados disponíveis", ha='center', va='center')

        # Gráfico 4: Vendas ao Longo do Tempo (Gráfico de Linhas)
        if "Sale_Date" in dados.columns and "Sales_Amount" in dados.columns:
            dados["Sale_Date"] = pd.to_datetime(dados["Sale_Date"], errors="coerce")
            vendas_tempo = dados.groupby("Sale_Date")["Sales_Amount"].sum().dropna()
            if not vendas_tempo.empty:
                vendas_tempo.plot(kind="line", ax=ax4, marker='o', color='#2E8B57', linewidth=2)
                ax4.set_title("Vendas ao Longo do Tempo")
                ax4.set_xlabel("Data")
                ax4.set_ylabel("Valor (R$)")
            else:
                ax4.text(0.5, 0.5, "Sem dados disponíveis", ha='center', va='center')

        plt.tight_layout()
        return fig

    # Função para exportar para PDF
    def exportar_pdf(kpis, filename="relatorio_kpis.pdf"):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        title = Paragraph("Relatório de KPIs", styles['Heading1'])
        elements.append(title)
        elements.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))

        data = [["KPI", "Valor"]]
        for kpi, valor in kpis.items():
            if isinstance(valor, (int, float)):
                data.append([kpi, f"{valor:.2f}"])
            else:
                data.append([kpi, str(valor)])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer

    # Função para exportar para CSV
    def exportar_csv(kpis, filename="relatorio_kpis.csv"):
        df_kpis = pd.DataFrame(list(kpis.items()), columns=["KPI", "Valor"])
        buffer = BytesIO()
        df_kpis.to_csv(buffer, index=False)
        buffer.seek(0)
        return buffer

    # Interface Streamlit
    st.title("Gerador de Relatórios de KPIs com Gráficos")
    st.write("Carregue um arquivo Excel para gerar relatórios e visualizar dados.")

    # Upload de arquivo com feedback
    with st.container():
        st.subheader("Upload de Arquivo")
        arquivo = st.file_uploader("Carregue o arquivo Excel (.xlsx)", type=["xlsx"], help="Selecione um arquivo Excel com dados de vendas, custos, etc.")
        if st.button("Processar Arquivo", type="primary"):
            with st.spinner("Processando o arquivo..."):
                dados = processar_dados(arquivo)
                if dados is not None:
                    st.success("Arquivo processado com sucesso!")
                else:
                    st.error("Erro ao processar o arquivo. Verifique o formato ou os dados.")

    # Inicializar kpis como dicionário vazio
    kpis = {}

    if arquivo is not None:
        dados = processar_dados(arquivo)
        if dados is not None:
            # Calcular KPIs
            kpis = calcular_kpis(dados)
            
            # Exibir KPIs em colunas
            st.subheader("KPIs Calculados")
            col1, col2 = st.columns(2)
            with col1:
                for kpi, valor in list(kpis.items())[:len(kpis)//2]:
                    if isinstance(valor, (int, float)):
                        st.write(f"**{kpi}:** {valor:.2f}")
                    else:
                        st.write(f"**{kpi}:** {valor}")
            with col2:
                for kpi, valor in list(kpis.items())[len(kpis)//2:]:
                    if isinstance(valor, (int, float)):
                        st.write(f"**{kpi}:** {valor:.2f}")
                    else:
                        st.write(f"**{kpi}:** {valor}")

            # Exibir gráficos
            st.subheader("Gráficos Didáticos")
            fig = criar_graficos(dados)
            if fig is not None:
                st.pyplot(fig)

            # Filtros interativos
            st.subheader("Filtros Interativos")
            data_inicio = st.date_input("Data de Início", dados["Sale_Date"].min() if "Sale_Date" in dados.columns else datetime.now())
            data_fim = st.date_input("Data de Fim", dados["Sale_Date"].max() if "Sale_Date" in dados.columns else datetime.now())
            categoria = st.selectbox("Filtrar por Categoria", ["Todos"] + list(dados["Product_Category"].unique()) if "Product_Category" in dados.columns else ["Todos"])
            canal = st.selectbox("Filtrar por Canal", ["Todos"] + list(dados["Sales_Channel"].unique()) if "Sales_Channel" in dados.columns else ["Todos"])

            dados_filtrados = dados.copy()
            if "Sale_Date" in dados.columns:
                dados_filtrados = dados_filtrados[(dados_filtrados["Sale_Date"].dt.date >= data_inicio) & (dados_filtrados["Sale_Date"].dt.date <= data_fim)]
            if categoria != "Todos" and "Product_Category" in dados.columns:
                dados_filtrados = dados_filtrados[dados_filtrados["Product_Category"] == categoria]
            if canal != "Todos" and "Sales_Channel" in dados.columns:
                dados_filtrados = dados_filtrados[dados_filtrados["Sales_Channel"] == canal]

            kpis_filtrados = calcular_kpis(dados_filtrados)
            st.subheader("KPIs Filtrados")
            for kpi, valor in kpis_filtrados.items():
                if isinstance(valor, (int, float)):
                    st.write(f"**{kpi}:** {valor:.2f}")
                else:
                    st.write(f"**{kpi}:** {valor}")

            # Chat simples para solicitar relatórios
            st.subheader("Chat para Solicitar Relatórios")
            mensagem = st.text_input("Digite sua solicitação (ex.: 'Quero relatório de vendas por categoria')")
            if st.button("Enviar"):
                if "vendas por categoria" in mensagem.lower() and "Product_Category" in dados.columns:
                    st.write("### Relatório de Vendas por Categoria")
                    vendas_categoria = dados.groupby("Product_Category")["Sales_Amount"].sum().dropna()
                    if not vendas_categoria.empty:
                        st.write(vendas_categoria)
                    else:
                        st.write("Sem dados disponíveis para este relatório.")
                elif "vendas por canal" in mensagem.lower() and "Sales_Channel" in dados.columns:
                    st.write("### Relatório de Vendas por Canal")
                    vendas_canal = dados.groupby("Sales_Channel")["Sales_Amount"].sum().dropna()
                    if not vendas_canal.empty:
                        st.write(vendas_canal)
                    else:
                        st.write("Sem dados disponíveis para este relatório.")
                elif "vendas por região" in mensagem.lower() and "Region_and_Sales_Rep" in dados.columns:
                    st.write("### Relatório de Vendas por Região/Representante")
                    vendas_regiao = dados.groupby("Region_and_Sales_Rep")["Sales_Amount"].sum().dropna()
                    if not vendas_regiao.empty:
                        st.write(vendas_regiao)
                    else:
                        st.write("Sem dados disponíveis para este relatório.")
                elif "lucro por categoria" in mensagem.lower() and "Product_Category" in dados.columns:
                    st.write("### Relatório de Lucro por Categoria")
                    lucro_categoria = (dados.groupby("Product_Category")["Sales_Amount"].sum() - dados.groupby("Product_Category")["Unit_Cost"].sum() * dados.groupby("Product_Category")["Quantity_Sold"].sum()).dropna()
                    if not lucro_categoria.empty:
                        st.write(lucro_categoria)
                    else:
                        st.write("Sem dados disponíveis para este relatório.")
                else:
                    st.write("Desculpe, não entendi. Tente 'vendas por categoria', 'vendas por canal', 'vendas por região', ou 'lucro por categoria'.")

            # Botões interativos para categorias
            st.subheader("Navegação por Categorias")
            opcoes = ["Product_Category", "Sales_Channel", "Region_and_Sales_Rep"]
            categoria_selecionada = st.selectbox("Selecione uma categoria para analisar", opcoes)

            if st.button("Gerar Relatório"):
                if categoria_selecionada == "Product_Category" and "Sales_Amount" in dados.columns:
                    st.write("### Vendas por Categoria")
                    vendas = dados.groupby("Product_Category")["Sales_Amount"].sum().dropna()
                    if not vendas.empty:
                        st.write(vendas)
                        fig, ax = plt.subplots(figsize=(8, 6))
                        sns.barplot(x=vendas.index, y=vendas.values, ax=ax, palette="Blues_d")
                        ax.set_title("Vendas por Categoria")
                        ax.tick_params(axis='x', rotation=45)
                        st.pyplot(fig)
                    else:
                        st.write("Sem dados disponíveis para este relatório.")
                elif categoria_selecionada == "Sales_Channel" and "Sales_Amount" in dados.columns:
                    st.write("### Vendas por Canal")
                    vendas = dados.groupby("Sales_Channel")["Sales_Amount"].sum().dropna()
                    if not vendas.empty:
                        st.write(vendas)
                        fig, ax = plt.subplots(figsize=(8, 6))
                        vendas.plot(kind="pie", ax=ax, autopct='%1.1f%%', colors=['#FF6B6B', '#4ECDC4', '#45B7D1'])
                        ax.set_title("Vendas por Canal")
                        st.pyplot(fig)
                    else:
                        st.write("Sem dados disponíveis para este relatório.")
                elif categoria_selecionada == "Region_and_Sales_Rep" and "Sales_Amount" in dados.columns:
                    st.write("### Vendas por Região/Representante")
                    vendas = dados.groupby("Region_and_Sales_Rep")["Sales_Amount"].sum().dropna()
                    if not vendas.empty:
                        st.write(vendas)
                        fig, ax = plt.subplots(figsize=(8, 6))
                        sns.barplot(x=vendas.index, y=vendas.values, ax=ax, palette="Purples_d")
                        ax.set_title("Vendas por Região/Representante")
                        ax.tick_params(axis='x', rotation=45)
                        st.pyplot(fig)
                    else:
                        st.write("Sem dados disponíveis para este relatório.")

            # Exportação de relatórios
            st.subheader("Exportar Relatórios")
            col_exp1, col_exp2, col_exp3 = st.columns(3)
            with col_exp1:
                if st.button("Exportar para Excel"):
                    if kpis:
                        df_kpis = pd.DataFrame(list(kpis.items()), columns=["KPI", "Valor"])
                        df_kpis.loc[len(df_kpis)] = ["Data do Relatório", datetime.now().strftime('%d/%m/%Y %H:%M')]
                        output = BytesIO()
                        writer = pd.ExcelWriter(output, engine='openpyxl')
                        df_kpis.to_excel(writer, index=False, sheet_name='KPIs')
                        writer.close()
                        output.seek(0)
                        st.download_button(
                            label="Baixar Excel",
                            data=output.getvalue(),
                            file_name="relatorio_kpis.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            with col_exp2:
                if st.button("Exportar para PDF"):
                    if kpis:
                        pdf_buffer = exportar_pdf(kpis)
                        st.download_button(
                            label="Baixar PDF",
                            data=pdf_buffer.getvalue(),
                            file_name="relatorio_kpis.pdf",
                            mime="application/pdf"
                        )
            with col_exp3:
                if st.button("Exportar para CSV"):
                    if kpis:
                        csv_buffer = exportar_csv(kpis)
                        st.download_button(
                            label="Baixar CSV",
                            data=csv_buffer.getvalue(),
                            file_name="relatorio_kpis.csv",
                            mime="text/csv"
                        )

    # Estilização visual avançada
    st.markdown("""
    <style>
    .stApp {
        background-color: #f0f4f8;
        font-family: 'Arial', sans-serif;
        padding: 20px;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 16px;
        transition: background-color 0.3s, transform 0.3s;
    }
    .stButton>button:hover {
        background-color: #45a049;
        transform: scale(1.05);
    }
    .stSelectbox, .stTextInput, .stDateInput {
        border-radius: 8px;
        border: 2px solid #4CAF50;
        padding: 8px;
    }
    .stHeader {
        background-color: #2c3e50;
        color: white;
        padding: 10px;
        border-radius: 8px;
    }
    .stProgress > div > div > div {
        background-color: #4CAF50;
    }
    </style>
    """, unsafe_allow_html=True)