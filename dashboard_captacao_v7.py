# dashboard_captacao_v7.py

import streamlit as st
import pandas as pd
from io import BytesIO
from apify_client import ApifyClient

# Configuração da página
st.set_page_config(page_title="Captação Imobiliária Bahia", page_icon="🏠", layout="wide")

# --- SEGURANÇA ---
try:
    APIFY_API_TOKEN = st.secrets["APIFY_API_TOKEN"]
except Exception:
    st.error("❌ Erro de Configuração: O Token da Apify não foi encontrado nos Secrets.")
    st.stop()

ACTOR_ID = "israeloriente/olx-brasil-imoveis-scraper"

st.title("🏠 Painel de Captação Imobiliária - EXCLUSIVO BAHIA")
st.sidebar.header("⚙️ Filtros de Busca")

# --- FILTROS DE LOCALIZAÇÃO ---
# Mapeamento de Cidades e seus Slugs/Regiões na OLX
cidades_config = {
    "Salvador": {"slug": "salvador", "regiao": "grande-salvador"},
    "Lauro de Freitas": {"slug": "lauro-de-freitas", "regiao": "grande-salvador"},
    "Camaçari": {"slug": "camacari", "regiao": "grande-salvador"},
    "Feira de Santana": {"slug": "feira-de-santana", "regiao": "feira-de-santana-e-regiao"},
    "Vitória da Conquista": {"slug": "vitoria-da-conquista", "regiao": "vitoria-da-conquista-e-regiao"}
}

cidade = st.sidebar.selectbox("🏙️ Escolha a Cidade", options=list(cidades_config.keys()), index=0)

# Bairros por Cidade
bairros_por_cidade = {
    "Salvador": ["Stella Maris", "Praia do Flamengo", "Itapuã", "Pituaçu", "Imbuí", "Caminho das Árvores", "Graça", "Barra"],
    "Lauro de Freitas": ["Vilas do Atlântico", "Buraquinho", "Ipitanga", "Estrada do Coco"],
    "Camaçari": ["Guarajuba", "Itacimirim", "Arembepe", "Busca Vida"],
    "Feira de Santana": ["Santa Mônica", "SIM", "Capuchinhos"],
    "Vitória da Conquista": ["Candeias", "Recreio"]
}

bairro = st.sidebar.selectbox("📍 Escolha o Bairro", options=bairros_por_cidade.get(cidade, ["Todos"]))

# --- FILTROS DE IMÓVEL ---
tipo_transacao = st.sidebar.radio("💰 Transação", ["Venda", "Aluguel"])
preco_min = st.sidebar.number_input("Preço Mínimo (R$)", value=350000, step=50000)
quartos_min = st.sidebar.slider("Quartos Mínimos", 1, 5, 2)
apenas_particular = st.sidebar.checkbox("✅ Apenas Proprietários (Particulares)", value=True)

if st.button("🔍 Iniciar Captação na Bahia", use_container_width=True):
    with st.spinner(f"Buscando leads em {bairro}, {cidade}..."):
        try:
            client = ApifyClient(APIFY_API_TOKEN)
            
            # --- CONSTRUÇÃO DA URL TRAVADA NA BAHIA ---
            config = cidades_config[cidade]
            regiao = config["regiao"]
            cidade_slug = config["slug"]
            bairro_slug = bairro.lower().replace(" ", "-")
            
            # Padrão de URL da OLX para evitar resultados de SP/outros estados:
            # https://www.olx.com.br/imoveis/venda/estado-ba/regiao-de-salvador/salvador/stella-maris
            if bairro == "Todos":
                search_url = f"https://www.olx.com.br/imoveis/{tipo_transacao.lower()}/estado-ba/{regiao}/{cidade_slug}"
            else:
                search_url = f"https://www.olx.com.br/imoveis/{tipo_transacao.lower()}/estado-ba/{regiao}/{cidade_slug}/{bairro_slug}"
            
            st.info(f"🌐 URL de Busca (Travada na Bahia): {search_url}")
            
            run_input = {
                "startUrls": [{"url": search_url}],
                "maxItems": 100,
                "is_professional": not apenas_particular,
                "minPrice": preco_min,
                "minRooms": quartos_min
            }
            
            run = client.actor(ACTOR_ID).call(run_input=run_input)
            
            if run and run.get('status') == 'SUCCEEDED':
                dataset = client.dataset(run["defaultDatasetId"])
                leads = list(dataset.iterate_items())
                
                if leads:
                    df = pd.DataFrame(leads)
                    # Filtro extra de segurança no código para garantir que a localização contenha 'BA' ou a cidade
                    if 'location' in df.columns:
                        df = df[df['location'].str.contains(f"BA|{cidade}", case=False, na=True)]
                    
                    st.success(f"✅ {len(df)} leads reais encontrados na Bahia!")
                    
                    # Mapeamento flexível de colunas
                    def find_col(possible_names, df):
                        for name in possible_names:
                            if name in df.columns: return name
                        return None

                    display_data = {}
                    for label, keys in {
                        "Título": ["title", "subject"],
                        "Preço": ["price", "priceValue"],
                        "Quartos": ["rooms", "quartos"],
                        "Área": ["area", "size"],
                        "Contato": ["contact", "phone"],
                        "URL": ["url", "link"]
                    }.items():
                        col = find_col(keys, df)
                        if col: display_data[label] = df[col]

                    if display_data:
                        st.dataframe(pd.DataFrame(display_data), use_container_width=True)
                    else:
                        st.dataframe(df.head(10))
                    
                    # Download
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    st.download_button("📊 Baixar Excel Completo", output.getvalue(), f"leads_BA_{cidade_slug}.xlsx", use_container_width=True)
                else:
                    st.warning(f"Nenhum imóvel encontrado em {bairro}, {cidade}. Verifique os filtros.")
            else:
                st.error("Falha na execução do scraper na Apify.")
        except Exception as e:
            st.error(f"Erro: {e}")

st.markdown("---")
st.caption("Desenvolvido por Manus AI | Captação Inteligente v7 - Foco Total Bahia")
