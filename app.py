import streamlit as st
import pandas as pd
import requests
import urllib.parse
import csv
import io
import os

# --- Configurações da API (Lendo de forma segura do Streamlit Secrets) ---
# O Streamlit Cloud lê as chaves do arquivo .streamlit/secrets.toml
try:
    API_KEY = st.secrets["google_api"]["api_key"]
    CX_ID = st.secrets["google_api"]["cx_id"]
except KeyError:
    st.error("ERRO: Chaves da API não configuradas. Por favor, crie o arquivo .streamlit/secrets.toml.")
    st.stop()

API_URL = "https://www.googleapis.com/customsearch/v1"

# --- Biblioteca de Dorks (Todas as Dorks Possíveis ) ---
DORK_LIBRARY = {
    "Proprietário Direto (Redes Sociais)": [
        'site:facebook.com "#vendasemcomissao"',
        'site:facebook.com "#diretocomproprietario"',
        'site:instagram.com "#vendasemcomissao"',
        'site:instagram.com "#diretocomproprietario"',
        'site:facebook.com "vende-se" "proprietário"',
        'site:instagram.com "aluga-se" "proprietário"',
        'site:facebook.com "motivo de viagem" "mudar"',
        'site:facebook.com "preciso vender urgente"',
    ],
    "Oportunidades (Leilões/Editais)": [
        'filetype:pdf "lista de imóveis" "venda"',
        'filetype:xls "imóveis" "leilão"',
        'site:caixa.gov.br "venda direta"',
        'site:bb.com.br "imóveis" "leilão"',
        'filetype:pdf "edital" "imóveis"',
    ],
    "Parcerias com Corretores": [
        'site:linkedin.com "corretor de imóveis" "parceria"',
        'site:facebook.com "corretor" "parceria" "Salvador"',
        'site:linkedin.com "corretor" "prospecção" "Salvador"',
        'site:facebook.com "tenho cliente" "buscando imóvel"',
    ],
    "Anúncios com Contato Direto": [
        '"tratar direto com o proprietário"',
        '"contato no privado"',
        '"sem comissão"',
        '"aceito proposta"',
        '"abaixei o preço"',
    ],
    "Busca por Termos de Cliente (Demanda)": [
        '"quero comprar apartamento" "Salvador"',
        '"buscando casa" "Pituba"',
        '"procuro imóvel" "financiamento"',
        '"alugar sem fiador"',
    ]
}

# --- Função de Busca e Extração com API (Adaptada para Streamlit) ---

@st.cache_data(ttl=3600) # Cache para evitar chamadas repetidas à API
def extrair_links_api(dork, local, data_filter, num_paginas):
    links_encontrados = []
    
    # Variável para sinalizar erro de cota
    if 'cota_excedida' not in st.session_state:
        st.session_state['cota_excedida'] = False
    
    # Exclusões para focar no proprietário
    exclusoes = '-corretor -imobiliária -creci -"construtora" -incorporadora'
    
    # Combina a dork base com o local e exclusões
    full_dork = f'{dork} "{local}" {exclusoes}'
    
    for pagina in range(num_paginas):
        start_index = pagina * 10 + 1
        
        if start_index > 91: # Limite da API
            break
            
        params = {
            "key": API_KEY,
            "cx": CX_ID,
            "q": full_dork,
            "num": 10,
            "start": start_index,
        }
        
        if data_filter != "Sempre":
            # Filtro de tempo para a API (d1=24h, w1=7d)
            time_code = "d1" if data_filter == "Últimas 24h" else "w1"
            params["sort"] = f"date:r:{time_code}"
            
        try:
            response = requests.get(API_URL, params=params, timeout=15)
            
            if response.status_code == 429:
                st.session_state['cota_excedida'] = True
                st.error("🚨 COTA DA API EXCEDIDA (Erro 429). Use o modo de Busca Manual.")
                return links_encontrados
            
            if response.status_code != 200:
                st.error(f"Erro na API ({response.status_code}): {response.text}")
                return links_encontrados
                
            data = response.json()
            
            if 'items' in data:
                for item in data['items']:
                    link = item.get('link')
                    if link:
                        # Limpeza básica do link
                        if '?' in link:
                            link = link.split('?')[0]
                        
                        links_encontrados.append({
                            'Link': link,
                            'Título': item.get('title'),
                            'Snippet': item.get('snippet'),
                            'Dork Base': dork,
                            'Página': pagina + 1
                        })
            else:
                # Se não houver mais resultados, para a paginação
                break
                
        except requests.exceptions.RequestException as e:
            st.error(f"Erro de conexão: {e}")
            break
            
    if links_encontrados:
        return pd.DataFrame(links_encontrados)
    else:
        # Retorna uma lista vazia se não houver links, evitando o AttributeError
        return []

# --- Interface Streamlit ---

st.set_page_config(layout="wide", page_title="Painel de Prospecção Imobiliária (Deep Search)")

st.title("🏠 Painel de Prospecção Imobiliária (Deep Search)")
st.markdown("Use a inteligência das Google Dorks para encontrar imóveis e parcerias.")

# --- Configurações do Usuário ---
st.sidebar.header("⚙️ Configurações de Busca")

local_input = st.sidebar.text_input("Cidade/Bairro (Ex: Salvador Pituba)", "Salvador")

data_filter = st.sidebar.radio(
    "Filtro de Tempo (Recência)",
    ("Últimas 24h", "Última Semana", "Sempre")
)

num_paginas = st.sidebar.slider(
    "Profundidade da Busca (Páginas)",
    min_value=1, max_value=10, value=1, step=1,
    help="Cada página busca 10 resultados. O máximo é 10 páginas (100 resultados)."
)

# --- Seleção de Dorks ---
st.sidebar.header("🔍 Tipos de Dorks")
dorks_selecionadas = []
for categoria, dorks in DORK_LIBRARY.items():
    st.sidebar.subheader(categoria)
    for dork in dorks:
        if st.sidebar.checkbox(dork, value=True):
            dorks_selecionadas.append(dork)

# --- Botão de Execução ---
if st.sidebar.button("🚀 Iniciar Busca Profunda"):
    if not local_input:
        st.error("Por favor, insira a Cidade/Bairro para iniciar a busca.")
    elif not dorks_selecionadas:
        st.error("Por favor, selecione pelo menos uma Dork para buscar.")
    else:
        st.info(f"Iniciando busca em **{local_input}** para **{len(dorks_selecionadas)}** Dorks, com profundidade de **{num_paginas}** página(s).")
        
        # Lista para armazenar todos os resultados
        resultados_finais = []
        
        # Barra de progresso
        progress_bar = st.progress(0)
        
        for i, dork in enumerate(dorks_selecionadas):
            # Executa a busca e recebe o DataFrame (ou lista vazia em caso de erro/sem resultados)
            df_resultados = extrair_links_api(dork, local_input, data_filter, num_paginas)
            
            # O erro de AttributeError: 'list' object has no attribute 'empty' é corrigido aqui
            # O retorno da função extrair_links_api é uma lista vazia [] em caso de erro/sem resultados
            if isinstance(df_resultados, pd.DataFrame) and not df_resultados.empty:
                resultados_finais.append(df_resultados)
            
            # Se a cota excedeu, para o loop
            if st.session_state['cota_excedida']:
                break
            
            # Atualiza a barra de progresso
            progress_bar.progress((i + 1) / len(dorks_selecionadas))

        # Combina todos os DataFrames e remove duplicatas
        if resultados_finais:
            df_final = pd.concat(resultados_finais).drop_duplicates(subset=['Link']).reset_index(drop=True)
            
            st.success(f"✅ Busca concluída! Encontrados {len(df_final)} links únicos.")
            
            # Exibe a tabela de resultados
            st.subheader("Resultados Encontrados")
            st.dataframe(df_final[['Link', 'Título', 'Snippet', 'Dork Base']], use_container_width=True)
            
            # Botão de Download CSV
            csv_export = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Resultados em CSV",
                data=csv_export,
                file_name=f'prospeccao_{local_input.replace(" ", "_").lower()}_{data_filter.replace(" ", "_").lower()}.csv',
                mime='text/csv',
            )
        elif st.session_state['cota_excedida']:
            st.warning("A busca automática parou devido ao limite de cota da API. Use o modo de Busca Manual abaixo.")
        else:
            st.warning("Nenhum resultado encontrado com os filtros e dorks selecionadas.")
            
        # --- Modo de Busca Manual (Backup) ---
        st.subheader("Modo de Busca Manual (Backup)")
        st.markdown("Se a cota da API esgotar, use os links abaixo para buscar manualmente no Google.")
        
        exclusoes = '-corretor -imobiliária -creci -"construtora" -incorporadora'
        for dork in dorks_selecionadas:
            full_dork = f'{dork} "{local_input}" {exclusoes}'
            url_manual = f"https://www.google.com/search?q={urllib.parse.quote(full_dork )}"
            st.markdown(f"[{dork} - Abrir no Google]({url_manual})")

st.sidebar.markdown("---")
st.sidebar.markdown("Desenvolvido por Manus AI")
