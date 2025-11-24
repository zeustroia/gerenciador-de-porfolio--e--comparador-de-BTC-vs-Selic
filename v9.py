import json
import os
import sys
from datetime import datetime
import re

try:
    import requests
except ImportError:
    requests = None

ARQUIVO_DADOS = "carteira.json"

# --- FUNÇÕES DE LIMPEZA E FORMATAÇÃO VISUAL (BR) ---

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def formatar_brl(valor):
    """Transforma float 2500.50 em string '2.500,50'"""
    us_format = f"{valor:,.2f}"
    return us_format.replace(',', 'X').replace('.', ',').replace('X', '.')

def formatar_data_iso(data_str):
    if not data_str:
        return datetime.now().strftime("%Y-%m-%d")
    data_str = data_str.strip().replace(' ', '/').replace('.', '/')
    try:
        data_obj = datetime.strptime(data_str, "%d/%m/%Y")
        return data_obj.strftime("%Y-%m-%d")
    except ValueError:
        return None

def ler_valor_monetario(mensagem):
    while True:
        entrada = input(mensagem).strip()
        if not entrada: continue
        if ',' in entrada:
            limpo = entrada.replace('.', '').replace(',', '.')
        else:
            limpo = entrada.replace('.', '')
        try:
            return float(limpo)
        except ValueError:
            print("❌ Valor inválido.")

def ler_quantidade_sats_ninja(mensagem):
    while True:
        entrada = input(mensagem).strip()
        if not entrada: continue
        apenas_numeros = re.sub(r'\D', '', entrada)
        if not apenas_numeros:
            print("❌ Digite um número.")
            continue
        try:
            sats = int(apenas_numeros)
            if sats <= 0: 
                print("❌ Maior que zero.")
                continue
            return sats
        except ValueError:
            print("❌ Erro.")

# --- BANCO DE DADOS (COM ORDENAÇÃO AUTOMÁTICA) ---

def carregar_carteira():
    if not os.path.exists(ARQUIVO_DADOS): return []
    try:
        with open(ARQUIVO_DADOS, "r") as f: 
            dados = json.load(f)
            
            # --- AQUI ESTÁ A MUDANÇA ---
            # Organiza a lista pela chave 'data' (formato YYYY-MM-DD funciona perfeito)
            # Assim que carrega, ele já põe em ordem cronológica
            dados.sort(key=lambda x: x['data'])
            
            return dados
    except: return []

def salvar_carteira(dados):
    # Antes de salvar, garantimos que está ordenado também
    dados.sort(key=lambda x: x['data'])
    with open(ARQUIVO_DADOS, "w") as f: json.dump(dados, f, indent=4)

# --- MÓDULO DE COMPRAS ---

def adicionar_compra():
    print("\n--- 💰 Nova Compra ---")
    
    while True:
        d = input("Data (DD MM AAAA) [Enter=Hoje]: ")
        data_iso = formatar_data_iso(d)
        if data_iso: break
        print("❌ Data inválida.")

    sats = ler_quantidade_sats_ninja("Quantidade em SATS (ex: 50.000): ")
    
    print("\nDigite o valor GASTO (Use vírgula para centavos!)")
    custo_total = ler_valor_monetario("Valor em Reais (R$): ")
    
    btc_fracao = sats / 100_000_000
    preco_calculado = 0.0
    if btc_fracao > 0:
        preco_calculado = custo_total / btc_fracao

    nova_compra = {
        "data": data_iso,
        "sats": sats,
        "custo": custo_total,
        "preco_historico": preco_calculado
    }

    carteira = carregar_carteira()
    carteira.append(nova_compra)
    salvar_carteira(carteira)
    
    print(f"\n✅ Compra Registrada!")
    print(f"   BTC: {sats/100000000:.8f}")
    print(f"   Gasto: R$ {formatar_brl(custo_total)}")
    print(f"   (Ref: R$ {formatar_brl(preco_calculado)})")
    
    # Aviso extra
    print("\nℹ️  A lista será reordenada automaticamente pela data.")
    input("\nPressione Enter para voltar...")

# --- VISUALIZAÇÃO ---

def listar_compras(pausa=True):
    carteira = carregar_carteira()
    print(f"\n{'ID':<2} | {'DATA':<10} | {'QUANTIDADE (BTC)':<16} | {'GASTO (R$)':<13} | {'COTAÇÃO REF'}")
    print("-" * 75)
    
    t_sats = 0
    t_custo = 0

    for i, item in enumerate(carteira):
        d = datetime.strptime(item['data'], "%Y-%m-%d").strftime("%d/%m/%y")
        
        btc_visual = f"{item['sats'] / 100_000_000:.8f}"
        
        p_hist = item.get('preco_historico', 0.0)
        if p_hist == 0 and item['sats'] > 0:
             p_hist = item['custo'] / (item['sats']/100000000)

        print(f"{i+1:<2} | {d:<10} | {btc_visual:<16} | {formatar_brl(item['custo']):<13} | R$ {formatar_brl(p_hist)}")
        
        t_sats += item['sats']
        t_custo += item['custo']

    print("-" * 75)
    
    btc_total = t_sats / 100_000_000
    pm = 0.0
    if btc_total > 0:
        pm = t_custo / btc_total

    print(f"TOTAL BTC:   {btc_total:.8f}")
    print(f"INVESTIDO:   R$ {formatar_brl(t_custo)}")
    print(f"PREÇO MÉDIO: R$ {formatar_brl(pm)}")
    
    if pausa: input("\nEnter para voltar...")
    return t_sats, t_custo, pm

def relatorio_lucro():
    t_sats, t_inv, pm = listar_compras(pausa=False)
    
    if t_sats == 0: input("\nVazio. Enter..."); return
    
    print("\n--- Cotação Atual ---")
    print("[1] Online (CoinGecko) | [2] Manual")
    op = input("Opção: ")
    
    cotacao_brl = 0.0
    cotacao_usd = 0.0
    
    if op == "1":
        if requests:
            try:
                print("Consultando...")
                url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl,usd"
                req = requests.get(url, timeout=5)
                dados = req.json()
                cotacao_brl = float(dados['bitcoin']['brl'])
                cotacao_usd = float(dados['bitcoin']['usd'])
            except:
                print("❌ Erro."); 
                cotacao_brl = ler_valor_monetario("Cotação R$: ")
                cotacao_usd = ler_valor_monetario("Cotação USD: ")
        else:
            cotacao_brl = ler_valor_monetario("Cotação R$: ")
            cotacao_usd = ler_valor_monetario("Cotação USD: ")
    else:
        cotacao_brl = ler_valor_monetario("Cotação R$: ")
        cotacao_usd = ler_valor_monetario("Cotação USD: ")

    qtd_btc = t_sats / 100_000_000
    patrimonio_brl = qtd_btc * cotacao_brl
    patrimonio_usd = qtd_btc * cotacao_usd
    lucro_reais = patrimonio_brl - t_inv
    
    lucro_porc = 0.0
    if t_inv > 0:
        lucro_porc = ((patrimonio_brl - t_inv) / t_inv) * 100

    dolar_imp = cotacao_brl / cotacao_usd if cotacao_usd > 0 else 0
    sats_real = int(100_000_000 / cotacao_brl) if cotacao_brl > 0 else 0

    print("\n" + "="*40)
    print(f"💵 Dólar Implícito: R$ {formatar_brl(dolar_imp)}")
    print(f"🛒 Poder de Compra: 1 BRL = {sats_real} sats")
    print("-" * 40)
    print(f"🇧🇷 SALDO: R$ {formatar_brl(patrimonio_brl)}")
    print(f"🇺🇸 SALDO:  $ {formatar_brl(patrimonio_usd)}")
    print("-" * 40)
    print(f"📉 Investido:   R$ {formatar_brl(t_inv)}")
    
    cor = "✅" if lucro_reais >= 0 else "🔻"
    print(f"{cor} Resultado:   R$ {formatar_brl(lucro_reais)} ({formatar_brl(lucro_porc)}%)")
    print("="*40)
    input("\nEnter...")

def excluir_compra():
    carteira = carregar_carteira()
    if not carteira: print("Vazio."); return
    listar_compras(pausa=False)
    try:
        # ATENÇÃO: Como a lista é reordenada ao carregar, o ID visual
        # agora corresponde ao ID real da lista ordenada. Tudo funciona!
        idx = int(input("\nID para excluir (0 cancela): ")) - 1
        if 0 <= idx < len(carteira):
            removido = carteira.pop(idx)
            salvar_carteira(carteira)
            print(f"✅ Removido.")
    except: pass

def main():
    while True:
        limpar_tela()
        print("Gerenciador de Portfólio BTC")
        print("1. Adicionar Compra")
        print("2. Histórico & Preço Médio")
        print("3. Relatório Lucro")
        print("4. Excluir Registro")
        print("5. Sair")
        op = input("\nOpção: ")
        if op == '1': adicionar_compra()
        elif op == '2': listar_compras()
        elif op == '3': relatorio_lucro()
        elif op == '4': excluir_compra()
        elif op == '5': sys.exit()

if __name__ == "__main__":
    main()

