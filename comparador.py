import json
import os
import sys
import requests
from datetime import datetime, timedelta
import plotext as plt
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAÇÕES ---
ARQUIVO_DADOS = "carteira.json"
ARQUIVO_SELIC_CSV = "selic.csv"  # O arquivo que você vai baixar se der erro

# --- UTILITÁRIOS ---

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def formatar_brl(valor):
    return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def carregar_carteira():
    if not os.path.exists(ARQUIVO_DADOS):
        print(f"❌ Arquivo {ARQUIVO_DADOS} não encontrado.")
        return []
    try:
        with open(ARQUIVO_DADOS, "r") as f:
            dados = json.load(f)
            dados.sort(key=lambda x: x['data']) # Ordena cronologicamente
            return dados
    except: return []

# --- MOTOR DE LEITURA (CSV MANUAL) ---

def ler_csv_selic_local():
    """Lê o arquivo selic.csv se ele existir na pasta"""
    if not os.path.exists(ARQUIVO_SELIC_CSV):
        return None
    
    print(f"📂 Lendo arquivo local '{ARQUIVO_SELIC_CSV}'...")
    dados_dict = {}
    try:
        with open(ARQUIVO_SELIC_CSV, 'r', encoding='utf-8', errors='ignore') as f:
            linhas = f.readlines()
            for linha in linhas:
                # O formato do BCB geralmente é: data;valor (01/06/2021;0,016199)
                # Mas as vezes vem com aspas: "01/06/2021";"0,016199"
                linha = linha.strip().replace('"', '')
                if not linha or "data" in linha.lower(): continue
                
                partes = linha.split(';')
                if len(partes) < 2: partes = linha.split(',') # Tenta virgula caso mude
                
                if len(partes) >= 2:
                    data_str = partes[0]
                    valor_str = partes[1].replace(',', '.')
                    try:
                        dados_dict[data_str] = float(valor_str)
                    except: continue
        print(f"   ✅ {len(dados_dict)} registros carregados do arquivo!")
        return dados_dict
    except Exception as e:
        print(f"   ❌ Erro ao ler arquivo: {e}")
        return None

# --- MOTOR DE DOWNLOAD (COM LINK DE AJUDA) ---

def obter_dados_selic(carteira):
    # 1. Tenta ler arquivo local primeiro (Prioridade)
    dados_local = ler_csv_selic_local()
    if dados_local: return dados_local

    # 2. Se não tem arquivo, tenta baixar online
    print("⏳ Tentando baixar histórico online...")
    
    # Define datas
    if not carteira:
        data_ini = "01/01/2020"
    else:
        dt_primeira = datetime.strptime(carteira[0]['data'], "%Y-%m-%d") - timedelta(days=10)
        data_ini = dt_primeira.strftime("%d/%m/%Y")
    
    data_fim = datetime.now().strftime("%d/%m/%Y")
    
    # URL Mágica
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=csv&dataInicial={data_ini}&dataFinal={data_fim}"
    
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        req = requests.get(url, headers=headers, timeout=10, verify=False)
        if req.status_code == 200:
            # Salva o arquivo automaticamente para o futuro
            with open(ARQUIVO_SELIC_CSV, 'w', encoding='utf-8') as f:
                f.write(req.text)
            print("   ✅ Download concluído e salvo como 'selic.csv'!")
            return ler_csv_selic_local() # Lê o que acabou de baixar
        else:
            print(f"   ⚠️ Erro HTTP {req.status_code}")
    except Exception as e:
        print(f"   ⚠️ Falha na conexão: {e}")

    # 3. SE TUDO FALHAR: Pede ajuda ao humano
    limpar_tela()
    print("❌ NÃO FOI POSSÍVEL BAIXAR AUTOMATICAMENTE (Bloqueio do BCB)")
    print("   Mas não se preocupe! Você pode baixar manualmente.")
    print("\n   1. Copie o link abaixo e cole no seu navegador:")
    print("-" * 60)
    print(url)
    print("-" * 60)
    print("\n   2. O download do arquivo 'dados.csv' vai começar.")
    print(f"   3. Renomeie para '{ARQUIVO_SELIC_CSV}' e coloque nesta pasta.")
    print("   4. Rode este programa novamente.")
    
    input("\n   Pressione Enter para voltar ao menu...")
    return None

def calcular_aliquota_ir(dias):
    if dias <= 180: return 22.5
    elif dias <= 360: return 20.0
    elif dias <= 720: return 17.5
    else: return 15.0

# --- LÓGICA DE COMPARAÇÃO ---

def processar_comparacao():
    carteira = carregar_carteira()
    if not carteira: 
        input("Carteira vazia. Adicione compras primeiro."); return

    # 1. Cotação BTC
    print("⏳ Consultando preço do Bitcoin...")
    try:
        req = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl", timeout=5)
        cotacao_btc = float(req.json()['bitcoin']['brl'])
    except:
        val = input("❌ Erro API. Digite cotação BTC (R$): ").replace('.', '').replace(',', '.')
        cotacao_btc = float(val)

    # 2. SELIC (Onde a mágica acontece)
    dict_selic = obter_dados_selic(carteira)
    
    if not dict_selic:
        return # Se falhou tudo e o usuário não baixou o arquivo, volta pro menu

    # 3. Cálculos
    total_investido = 0.0
    total_btc_hoje = 0.0
    total_selic_liquida = 0.0
    hoje = datetime.now()

    print("\n--- Processando Dados ---")
    
    for item in carteira:
        try:
            data_compra = datetime.strptime(item['data'], "%Y-%m-%d")
        except: continue

        valor_aportado = item['custo']
        valor_btc_atual = (item['sats'] / 100_000_000) * cotacao_btc
        
        # CÁLCULO SELIC
        fator_acumulado = 1.0
        data_cursor = data_compra
        
        while data_cursor < hoje:
            data_str = data_cursor.strftime("%d/%m/%Y")
            if data_str in dict_selic:
                taxa_dia = dict_selic[data_str]
                fator_acumulado *= (1 + (taxa_dia / 100))
            data_cursor += timedelta(days=1)

        montante_bruto = valor_aportado * fator_acumulado
        lucro_bruto = montante_bruto - valor_aportado
        
        # IR
        dias_corridos = (hoje - data_compra).days
        aliquota = calcular_aliquota_ir(dias_corridos)
        imposto = lucro_bruto * (aliquota / 100)
        montante_liquido = montante_bruto - imposto

        total_investido += valor_aportado
        total_btc_hoje += valor_btc_atual
        total_selic_liquida += montante_liquido

    # Resultados
    lucro_btc = total_btc_hoje - total_investido
    lucro_selic = total_selic_liquida - total_investido
    
    perc_btc = (lucro_btc / total_investido) * 100 if total_investido > 0 else 0
    perc_selic = (lucro_selic / total_investido) * 100 if total_investido > 0 else 0

    limpar_tela()
    print("=== 🥊 BITCOIN vs SELIC (DADOS REAIS) ===")
    print(f"Cotação BTC: R$ {formatar_brl(cotacao_btc)}")
    print("-" * 60)
    print(f"{'METRICA':<20} | {'BITCOIN':<15} | {'SELIC LÍQUIDA'}")
    print("-" * 60)
    print(f"{'Patrimônio Final':<20} | R$ {formatar_brl(total_btc_hoje):<12} | R$ {formatar_brl(total_selic_liquida)}")
    print(f"{'Lucro Líquido':<20} | R$ {formatar_brl(lucro_btc):<12} | R$ {formatar_brl(lucro_selic)}")
    print(f"{'Rentabilidade %':<20} | {formatar_brl(perc_btc):<11}% | {formatar_brl(perc_selic)}%")
    print("-" * 60)

    diff = total_btc_hoje - total_selic_liquida
    if diff > 0:
        print(f"🏆 BITCOIN VENCE POR: R$ {formatar_brl(diff)}")
    else:
        print(f"🐢 SELIC VENCE POR:   R$ {formatar_brl(abs(diff))}")

    print("\n--- 📊 Gráfico ---")
    nomes = ["Investido", "Selic Líq", "Bitcoin"]
    valores = [total_investido, total_selic_liquida, total_btc_hoje]
    try:
        plt.simple_bar(nomes, valores, width=40, title="Patrimônio")
        plt.show()
    except: pass

    input("\nEnter para voltar...")

def simulador_preco_medio():
    # Mantive igual à versão anterior, pois já funciona
    limpar_tela()
    print("=== 🎯 CALCULADORA DE PREÇO MÉDIO ===")
    carteira = carregar_carteira()
    if not carteira: input("Vazio."); return

    total_sats = sum(c['sats'] for c in carteira)
    total_investido = sum(c['custo'] for c in carteira)
    total_btc = total_sats / 100_000_000
    pm_atual = total_investido / total_btc if total_btc > 0 else 0

    print(f"\n📊 Atual: {total_btc:.8f} BTC | Médio: R$ {formatar_brl(pm_atual)}")
    try:
        val = input("\nCotação AGORA? R$ ").replace('.', '').replace(',', '.')
        cotacao = float(val)
        val_alvo = input("Alvo de Médio? R$ ").replace('.', '').replace(',', '.')
        alvo = float(val_alvo)
    except: return

    if alvo <= cotacao or alvo >= pm_atual:
        print("❌ Impossível baixar para esse valor comprando acima dele.")
        input("Enter..."); return

    numerador = total_investido - (total_btc * alvo)
    denominador = alvo - cotacao
    btc_nec = numerador / denominador
    inv_nec = btc_nec * cotacao

    print("\n" + "="*40)
    print(f"🚀 ALVO: R$ {formatar_brl(alvo)}")
    print(f"Comprar: {btc_nec:.8f} BTC (R$ {formatar_brl(inv_nec)})")
    print("="*40)
    input("\nEnter...")

def main():
    while True:
        limpar_tela()
        print("=== 🧠 INTELLIGENCE MOD ===")
        print("1. Bitcoin vs Selic Real")
        print("2. Calculadora de Preço Médio")
        print("3. Sair")
        op = input("\nOpção: ")
        if op == '1': processar_comparacao()
        elif op == '2': simulador_preco_medio()
        elif op == '3': sys.exit()

if __name__ == "__main__":
    main()


#reenviar
