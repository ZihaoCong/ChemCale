import streamlit as st
import pandas as pd
import numpy as np
import io
import warnings

# 屏蔽 Pandas 警告
warnings.simplefilter(action='ignore', category=FutureWarning)

# ==========================================
# 1. UI 风格设置
# ==========================================
def inject_custom_css():
    st.markdown(
        """
        <style>
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        div.css-1r6slb0, div.css-12oz5g7 { background-color: #FFFFFF; border-radius: 10px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        h1, h2, h3 { color: #0EA5E9; }
        .stButton>button { background-color: #0EA5E9; color: white; border-radius: 6px; border: none; }
        .stButton>button:hover { background-color: #0284C7; color: white; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] { background-color: #E2E8F0; border-radius: 4px 4px 0 0; padding: 10px 20px; color: #475569; }
        .stTabs [aria-selected="true"] { background-color: #0EA5E9 !important; color: white !important; }
        </style>
        """, unsafe_allow_html=True
    )

# ==========================================
# 工具函数
# ==========================================
def to_excel(df: pd.DataFrame, sheet_name="Sheet1") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def calc_monomer_base(input_type: str, input_val: float, mw: float, target_dp: float):
    if mw <= 0 or input_val <= 0 or target_dp <= 0: return 0.0, 0.0
    n_monomer = input_val if input_type == "物质的量 (mmol)" else input_val / mw
    return n_monomer, n_monomer / target_dp

def calculate_reactants(df: pd.DataFrame, n_base: float) -> pd.DataFrame:
    res_df = df.copy()
    res_df.loc[res_df["角色"] == "Initiator", "当量(eq)"] = 1.0
    res_df["所需物质的量 (mmol)"] = 0.0
    res_df["理论质量 (mg)"] = 0.0
    res_df["添加体积 (μL)"] = np.nan
    
    if n_base > 0:
        res_df["所需物质的量 (mmol)"] = n_base * res_df["当量(eq)"]
        res_df["理论质量 (mg)"] = res_df["所需物质的量 (mmol)"] * res_df["分子量 (g/mol)"]
        mask_liquid = res_df["溶液浓度 (M)"].astype(float) > 0
        res_df.loc[mask_liquid, "添加体积 (μL)"] = (res_df.loc[mask_liquid, "所需物质的量 (mmol)"] / res_df.loc[mask_liquid, "溶液浓度 (M)"]) * 1000
    return res_df

# ==========================================
# 页面主框架
# ==========================================
def main():
    st.set_page_config(page_title="ChemLab Pro Matrix", layout="wide")
    inject_custom_css()
    
    st.title("🧪 化学与聚合物高精计算矩阵")
    st.caption("全模块已开启三位小数 (0.001) 高精度模式，支持动态单位换算。")
    
    # 调整了 Tab 的顺序
    tab1, tab2, tab3 = st.tabs(["🔗 聚合物专精 (Polymer)", "💧 储备液助手 (Stock Solutions)", "⚖️ 常规化学计量 (Stoichiometry)"])

    # ==========================================
    # Tab 1: 聚合物专精核算
    # ==========================================
    with tab1:
        st.header("1. 单体设定 (Monomer & Target DP)")
        col1, col2, col3 = st.columns(3)
        with col1: mon_name = st.text_input("主单体名称", value="Styrene")
        with col2: mon_mw = st.number_input("单体分子量 (g/mol)", min_value=0.001, value=104.150, format="%.3f")
        with col3: target_dp = st.number_input("目标聚合度 [M]/[I]", min_value=1.0, value=100.0)

        col4, col5, col6 = st.columns(3)
        with col4: mon_input_type = st.selectbox("单体投料设定", ["称重质量 (mg)", "物质的量 (mmol)"])
        with col5: mon_val = st.number_input("投料目标值", min_value=0.000, value=1041.500, step=100.0, format="%.3f")
        with col6: mon_conc = st.number_input("单体自身浓度 (M)", min_value=0.000, value=8.730, format="%.3f")

        n_monomer, n_base = calc_monomer_base(mon_input_type, mon_val, mon_mw, target_dp)
        mon_vol_ul = (n_monomer / mon_conc * 1000) if mon_conc > 0 else 0.0
        
        st.info(f"📌 **单体总量:** {n_monomer:.3f} mmol | **引发剂投料基准 ($n_{{base}}$):** {n_base:.3f} mmol")
        st.markdown("---")

        st.header("2. 催化体系加料配方")
        if "catalyst_system" not in st.session_state:
            st.session_state.catalyst_system = pd.DataFrame([
                {"角色": "Initiator", "名称": "EBiB", "分子量 (g/mol)": 195.050, "当量(eq)": 1.000, "溶液浓度 (M)": 0.100},
                {"角色": "Catalyst", "名称": "CuBr", "分子量 (g/mol)": 143.450, "当量(eq)": 1.000, "溶液浓度 (M)": 0.050},
                {"角色": "Ligand", "名称": "PMDETA", "分子量 (g/mol)": 173.300, "当量(eq)": 2.000, "溶液浓度 (M)": 0.100}
            ])

        edited_poly_df = st.data_editor(
            st.session_state.catalyst_system, 
            num_rows="dynamic", width="stretch",
            column_config={
                "角色": st.column_config.SelectboxColumn("角色", options=["Initiator", "Catalyst", "Ligand", "Additive"]),
                "分子量 (g/mol)": st.column_config.NumberColumn(min_value=0.001, format="%.3f"),
                "当量(eq)": st.column_config.NumberColumn(min_value=0.001, format="%.3f"),
                "溶液浓度 (M)": st.column_config.NumberColumn(min_value=0.0, format="%.3f")
            }
        )
        result_poly_df = calculate_reactants(edited_poly_df, n_base)

        monomer_row = pd.DataFrame([{
            "角色": "Monomer", "名称": mon_name, "分子量 (g/mol)": mon_mw, "当量(eq)": target_dp, 
            "溶液浓度 (M)": mon_conc if mon_conc > 0 else np.nan, 
            "所需物质的量 (mmol)": n_monomer, "理论质量 (mg)": n_monomer * mon_mw, 
            "添加体积 (μL)": mon_vol_ul if mon_conc > 0 else np.nan
        }])
        final_poly_recipe = pd.concat([monomer_row, result_poly_df], ignore_index=True)

        st.dataframe(final_poly_recipe.style.format({
            "分子量 (g/mol)": "{:.3f}", "当量(eq)": "{:.3f}", 
            "所需物质的量 (mmol)": "{:.3f}", "理论质量 (mg)": "{:.3f}", "添加体积 (μL)": "{:.3f}"
        }, na_rep="-"), width="stretch")
        st.markdown("---")

        st.header("3. 最终体系浓度核算")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1: extra_solvent_ml = st.number_input("额外添加的纯溶剂体积 (mL)", min_value=0.000, value=0.000, step=0.1, format="%.3f")
            
        total_vol_ml = (mon_vol_ul / 1000.0) + (result_poly_df["添加体积 (μL)"].fillna(0).sum() / 1000.0) + extra_solvent_ml
        
        with col_c2: st.metric("反应汇总总体积 (mL)", f"{total_vol_ml:.3f}")
        with col_c3:
            if total_vol_ml > 0: st.metric("实际单体浓度 $[M]_0$ (mol/L)", f"{(n_monomer / total_vol_ml):.3f}")

    # ==========================================
    # Tab 2: 储备液助手 (移动到了中间)
    # ==========================================
    with tab2:
        st.header("💧 储备液配制助手")
        st.caption("提示：若为固体，纯物密度设为 0；若为纯液体，填入实际密度自动计算移液体积和补加溶剂。")
        
        if "stock_system" not in st.session_state:
            st.session_state.stock_system = pd.DataFrame([
                {"试剂名称": "EBiB (液体)", "分子量 (g/mol)": 195.050, "纯物密度 (g/mL)": 1.490, "目标浓度 (mol/L)": 0.100, "目标配制体积 (mL)": 5.000},
                {"试剂名称": "CuBr (固体)", "分子量 (g/mol)": 143.450, "纯物密度 (g/mL)": 0.000, "目标浓度 (mol/L)": 0.050, "目标配制体积 (mL)": 10.000}
            ])

        stock_df = st.data_editor(
            st.session_state.stock_system, 
            num_rows="dynamic", width="stretch",
            column_config={
                "分子量 (g/mol)": st.column_config.NumberColumn(min_value=0.001, format="%.3f"),
                "纯物密度 (g/mL)": st.column_config.NumberColumn(min_value=0.000, format="%.3f"),
                "目标浓度 (mol/L)": st.column_config.NumberColumn(min_value=0.001, format="%.3f"),
                "目标配制体积 (mL)": st.column_config.NumberColumn(min_value=0.001, format="%.3f")
            }
        )
        
        stock_res = stock_df.copy()
        stock_res["所需 mmol"] = stock_res["目标浓度 (mol/L)"] * stock_res["目标配制体积 (mL)"]
        stock_res["理论质量 (mg)"] = stock_res["所需 mmol"] * stock_res["分子量 (g/mol)"]
        
        stock_res["需称取固体质量 (mg)"] = np.nan
        stock_res["需移取纯液体积 (μL)"] = np.nan
        stock_res["需补充溶剂体积 (mL)"] = np.nan
        
        mask_liquid = stock_res["纯物密度 (g/mL)"].astype(float) > 0
        mask_solid = ~mask_liquid
        
        stock_res.loc[mask_solid, "需称取固体质量 (mg)"] = stock_res.loc[mask_solid, "理论质量 (mg)"]
        stock_res.loc[mask_solid, "需补充溶剂体积 (mL)"] = stock_res.loc[mask_solid, "目标配制体积 (mL)"]
        
        stock_res.loc[mask_liquid, "需移取纯液体积 (μL)"] = stock_res.loc[mask_liquid, "理论质量 (mg)"] / stock_res.loc[mask_liquid, "纯物密度 (g/mL)"]
        stock_res.loc[mask_liquid, "需补充溶剂体积 (mL)"] = stock_res.loc[mask_liquid, "目标配制体积 (mL)"] - (stock_res.loc[mask_liquid, "需移取纯液体积 (μL)"] / 1000.0)

        st.subheader("💡 称量与移液指南")
        st.dataframe(stock_res[["试剂名称", "需称取固体质量 (mg)", "需移取纯液体积 (μL)", "需补充溶剂体积 (mL)"]].style.format({
            "需称取固体质量 (mg)": "{:.3f}", "需移取纯液体积 (μL)": "{:.3f}", "需补充溶剂体积 (mL)": "{:.3f}"
        }, na_rep="-"), width="stretch")

    # ==========================================
    # Tab 3: 常规化学计量 (移动到了最后)
    # ==========================================
    with tab3:
        st.header("⚖️ 反应物投料与产物理论产率核算")
        
        # 顶部单位选择器
        col_u1, col_u2 = st.columns(2)
        with col_u1: mass_unit = st.selectbox("全局质量单位", ["mg", "g"])
        with col_u2: amt_unit = st.selectbox("全局物质的量单位", ["mmol", "mol"])
        
        st.subheader("步骤 1: 设定基准物质 (Anchor)")
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1: gen_ref_name = st.text_input("基准物质名称", value="Reactant A (限量)")
        with col_r2: gen_ref_mw = st.number_input("分子量 (g/mol)", min_value=0.001, value=100.000, key="gen_ref_mw", format="%.3f")
        with col_r3: gen_ref_eq = st.number_input("基准当量(eq)", min_value=0.001, value=1.000, key="gen_ref_eq", format="%.3f")
        
        col_r4, col_r5, col_r6 = st.columns(3)
        with col_r4: gen_input_type = st.selectbox("基准设定依据", ["质量", "物质的量"])
        with col_r5: 
            unit_label = mass_unit if gen_input_type == "质量" else amt_unit
            gen_input_val = st.number_input(f"基准投料值 ({unit_label})", min_value=0.000, value=500.000, format="%.3f")
        with col_r6: gen_ref_purity = st.number_input("基准物质纯度 (%)", min_value=0.001, max_value=100.0, value=100.000, format="%.3f")

        # 将基准物质转换为绝对摩尔 (mol) 作为底层计算基座
        base_pure_mol = 0.0
        if gen_ref_mw > 0:
            if gen_input_type == "质量":
                actual_mass_g = gen_input_val if mass_unit == "g" else gen_input_val / 1000.0
                pure_mass_g = actual_mass_g * (gen_ref_purity / 100.0)
                base_pure_mol = pure_mass_g / gen_ref_mw
            else:
                actual_mol = gen_input_val if amt_unit == "mol" else gen_input_val / 1000.0
                base_pure_mol = actual_mol * (gen_ref_purity / 100.0)

        # 1 eq 对应的底层 mol
        system_base_mol = base_pure_mol / gen_ref_eq if gen_ref_eq > 0 else 0.0
        
        # 显示当前基准的量
        display_base_amt = base_pure_mol if amt_unit == "mol" else base_pure_mol * 1000.0
        st.info(f"🎯 **底层核算:** 该基准纯物质的量为 **{display_base_amt:.3f} {amt_unit}**。反应体系 1.0 eq = {(system_base_mol if amt_unit == 'mol' else system_base_mol * 1000.0):.3f} {amt_unit}。")
        st.markdown("---")

        st.subheader("步骤 2: 填写反应体系其他组分")
        if "general_rxn" not in st.session_state:
            st.session_state.general_rxn = pd.DataFrame([
                {"角色": "Reactant", "名称": "Reactant B", "分子量 (g/mol)": 150.000, "当量(eq)": 1.200, "纯度 (%)": 98.000},
                {"角色": "Product", "名称": "Target Product C", "分子量 (g/mol)": 232.000, "当量(eq)": 1.000, "纯度 (%)": 100.000}
            ])

        edited_gen_df = st.data_editor(
            st.session_state.general_rxn, 
            num_rows="dynamic", width="stretch",
            column_config={
                "角色": st.column_config.SelectboxColumn("角色", options=["Reactant", "Product", "Catalyst", "Additive"]),
                "分子量 (g/mol)": st.column_config.NumberColumn(min_value=0.001, format="%.3f"),
                "当量(eq)": st.column_config.NumberColumn(min_value=0.001, format="%.3f"),
                "纯度 (%)": st.column_config.NumberColumn(min_value=0.001, max_value=100.0, format="%.3f")
            }
        )

        res_gen_df = edited_gen_df.copy()
        
        # 1. 算底层理论所需 mol
        res_gen_df["_theo_mol"] = system_base_mol * res_gen_df["当量(eq)"]
        
        # 2. 转换为显示单位的物质的量
        amt_col_name = f"所需/生成量 ({amt_unit})"
        res_gen_df[amt_col_name] = res_gen_df["_theo_mol"] if amt_unit == "mol" else res_gen_df["_theo_mol"] * 1000.0
        
        # 3. 算底层理论纯质量 (g)
        res_gen_df["_theo_mass_g"] = res_gen_df["_theo_mol"] * res_gen_df["分子量 (g/mol)"]
        
        # 4. 根据纯度计算实际需称取的质量 (g)
        res_gen_df["_actual_mass_g"] = res_gen_df["_theo_mass_g"] / (res_gen_df["纯度 (%)"] / 100.0)
        
        # 5. 转换为显示单位的质量
        mass_col_name = f"目标质量/实际投料 ({mass_unit})"
        res_gen_df[mass_col_name] = res_gen_df["_actual_mass_g"] if mass_unit == "g" else res_gen_df["_actual_mass_g"] * 1000.0

        # 清理多余列并拼接基准行
        res_gen_df = res_gen_df.drop(columns=["_theo_mol", "_theo_mass_g", "_actual_mass_g"])
        
        gen_anchor_row = pd.DataFrame([{
            "角色": "Anchor (Limiting)", "名称": gen_ref_name, "分子量 (g/mol)": gen_ref_mw, 
            "当量(eq)": gen_ref_eq, "纯度 (%)": gen_ref_purity,
            amt_col_name: display_base_amt,
            mass_col_name: gen_input_val if gen_input_type == "质量" else (display_base_amt * gen_ref_mw / (1000 if amt_unit == 'mmol' and mass_unit == 'g' else 1)) 
        }])
        
        # 修正基准行的显示质量计算
        if gen_input_type == "质量":
            anchor_disp_mass = gen_input_val
        else:
            theo_g = base_pure_mol * gen_ref_mw
            act_g = theo_g / (gen_ref_purity / 100.0)
            anchor_disp_mass = act_g if mass_unit == "g" else act_g * 1000.0
        gen_anchor_row[mass_col_name] = anchor_disp_mass

        final_gen_recipe = pd.concat([gen_anchor_row, res_gen_df], ignore_index=True)

        st.dataframe(final_gen_recipe.style.format({
            "分子量 (g/mol)": "{:.3f}", "当量(eq)": "{:.3f}", "纯度 (%)": "{:.3f}",
            amt_col_name: "{:.3f}", mass_col_name: "{:.3f}"
        }), width="stretch")
        
        st.download_button("📥 导出常规反应计量表 (.xlsx)", data=to_excel(final_gen_recipe, "Stoichiometry"), file_name="stoichiometry.xlsx")

        st.markdown("---")
        
        # ==========================================
        # 质量-体积换算助手
        # ==========================================
        st.subheader("步骤 3: 质量 - 体积 智能换算助手")
        st.caption("针对纯液体反应物，输入上方计算得出的质量和查阅的密度，快速转换为移液体积。")
        
        col_v1, col_v2, col_v3, col_v4 = st.columns(4)
        with col_v1:
            v_mass_val = st.number_input("纯液体质量", min_value=0.000, value=100.000, format="%.3f")
        with col_v2:
            v_mass_unit = st.selectbox("输入质量单位", ["mg", "g"])
        with col_v3:
            v_density = st.number_input("液体密度 (g/mL)", min_value=0.001, value=1.000, format="%.3f")
        with col_v4:
            v_vol_unit = st.selectbox("输出体积单位", ["μL", "mL"])

        # 计算逻辑
        v_mass_g = v_mass_val if v_mass_unit == "g" else v_mass_val / 1000.0
        v_vol_ml = v_mass_g / v_density
        v_vol_final = v_vol_ml if v_vol_unit == "mL" else v_vol_ml * 1000.0

        st.success(f"🧪 **换算结果:** 需要移取 **{v_vol_final:.3f} {v_vol_unit}**")

if __name__ == "__main__":
    main()