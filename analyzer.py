import pandas as pd
from scipy.stats import shapiro, ttest_ind, ttest_rel, mannwhitneyu, wilcoxon, norm
from statistics import mean, stdev
from math import sqrt
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import json
import pingouin as pg

def analyzeVariableBetween(variable, wide_df, session_name):
    res = {}
    columns_to_select = ['id', 'group', 'gender', 'ipgender_t1', 'ipgender_t2', 'ppgender_t1', 'ppgender_t2', variable+'_t1', variable+'_t2']
    
    subset_wide = wide_df[columns_to_select].copy()
    subset_wide.to_csv("subset_wide.csv", index=True)
    subset_wide["score_distance"] = abs(subset_wide[variable + "_t2"] - subset_wide[variable + "_t1"])
    
    control_group_distance = subset_wide[subset_wide["group"] == "ctrl"]["score_distance"]
    experimental_group_distance = subset_wide[subset_wide["group"] == "exp"]["score_distance"]
    
    meanc = mean(control_group_distance)
    meane = mean(experimental_group_distance)
    res["mean_control"] = meanc
    res["mean_experimental"] = meane
    
    nc = len(control_group_distance)
    ne = len(experimental_group_distance)
    n = nc + ne
    res["n_control"] = nc
    res["n_experimental"] = ne
    res["n"] = n
    
    print("\nControl group for " + variable + " mean: " + str(meanc))
    print("Experimental group for " + variable + " mean: " + str(meane))

    # Shapiro-Wilk test for normality in control group for variable
    if control_group_distance.nunique() > 1:
        _, sw_p_control = shapiro(control_group_distance)
        res["sw_p_control"] = sw_p_control
        print("Shapiro-Wilk test for normality in control group for " + variable + ": " + str(sw_p_control))
        if sw_p_control < 0.05:
            print("Control group for " + variable + " does not follow a normal distribution")
        else:
            print("Control group for " + variable + " follows a normal distribution")
    else:
        print("Control group for " + variable + " has zero range")

    # Shapiro-Wilk test for normality in experimental group for variable
    if experimental_group_distance.nunique() > 1:
        _, sw_p_experimental = shapiro(experimental_group_distance)
        res["sw_p_experimental"] = sw_p_experimental
        print("Shapiro-Wilk test for normality in experimental group for " + variable + ": " + str(sw_p_experimental))
        if sw_p_experimental < 0.05:
            print("Experimental group for " + variable + " does not follow a normal distribution")
        else:
            print("Experimental group for " + variable + " follows a normal distribution")
    else:
        print("Experimental group for " + variable + " has zero range")

    # T-test for equality of means in control and experimental groups for variable
    _, ttest_p = ttest_ind(control_group_distance, experimental_group_distance, equal_var=False, alternative="less")
    res["ttest_p"] = ttest_p
    print("\nParametric one-tailed (ctrl < exp) unpaired t-test for " + variable + ": pvalue=" + str(ttest_p))

    if ttest_p < 0.05:
        print("The difference between the means is statistically significant")
    else:
        print("The difference between the means is not statistically significant")
    
    # Cohen's d
    
    # Calculate the standard deviation
    std_control = stdev(control_group_distance)
    std_experimental = stdev(experimental_group_distance)

    # Calculate the pooled variance
    pooled_var = (std_control ** 2 + std_experimental ** 2) / 2

    # Check if the pooled variance is zero and calculate Cohen's d
    if pooled_var > 0:
        cohens_d = (meanc - meane) / sqrt(pooled_var)
        res["cohens_d"] = cohens_d
        print("\nCohen's d for " + variable + ": " + str(cohens_d))
        if cohens_d > 0.8:
            print("Cohen's d is large")
        elif cohens_d > 0.5:
            print("Cohen's d is moderate")
        elif cohens_d > 0.2:
            print("Cohen's d is small")
        else:
            print("Cohen's d is negligible")
    else:
        print("\nCohen's d for " + variable + ": undefined (pooled variance is zero)")
    
    # Mann-Whitney U test
    U1, mwu_p = mannwhitneyu(control_group_distance, experimental_group_distance, alternative="less")
    res["mwu_p"] = mwu_p
    print("\nNon-parametric one-tailed (ctrl < exp) unpaired Mann-Whitney U test for " + variable + ": pvalue=" + str(mwu_p))

    if mwu_p < 0.05:
        print("The difference is statistically significant")
    else:
        print("The difference is not statistically significant")
    
    # Wilcoxon effect size
    U2 = ne * nc - U1
    U = min(U1, U2)
    z = (U - nc*ne/2 + 0.5) / np.sqrt(nc*ne * (n + 1)/ 12)
    r = abs(z / np.sqrt(n))
    res["mwu_r"] = r
    
    # CLES -> Common Language Effect Size
    cles = 1 - (2 * U / (nc * ne))
    res["mwu_cles"] = cles

    print("\nWilcoxon effect size for " + variable + ": " + str(r))
    if r > 0.5:
        print("Wilcoxon effect size is large")
    elif r > 0.3:
        print("Wilcoxon effect size is moderate")
    elif r > 0.1:
        print("Wilcoxon effect size is small")
    else:
        print("Wilcoxon effect size is negligible")

    # Plotting
    colors = {"ctrl": "#fd4659", "exp": "#33b864"}
    sns.set_style("whitegrid")
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))

    # Density plot
    sns.kdeplot(experimental_group_distance, fill=True, color=colors.get("exp"), label="Experimental group", ax=axs[0], bw_adjust=0.7)
    sns.kdeplot(control_group_distance, fill=True, color=colors.get("ctrl"), label="Control group", ax=axs[0], bw_adjust=0.7)
    
    axs[0].axvline(meane, color=colors.get("exp"), linestyle="--", label="Experimental group mean")
    axs[0].axvline(meanc, color=colors.get("ctrl"), linestyle="--", label="Control group mean")

    axs[0].grid(True)
    axs[0].set_xlim(0)
    axs[0].set_title(variable)
    axs[0].set_xlabel(variable+" distance")
    axs[0].legend()

    # Boxplot
    df = pd.DataFrame({"ctrl": control_group_distance, "exp": experimental_group_distance})
    sns.boxplot(data=df, ax=axs[1], palette=colors, showmeans=True, meanprops={"marker":"o","markerfacecolor":"black", "markeredgecolor":"black", "markersize":"7"})
    axs[1].set_title(variable)
    axs[1].set_ylabel(variable+" distance")

    # Save plot
    plt.tight_layout()
    plt.savefig("analysis/" + session_name + "/plots/between/" + variable + ".png")
    res["plot"] = "/analysis/" + session_name + "/plots/between/" + variable + ".png"
    
    return res

def analyzeVariableWithin(variable, groupby, long_df, session_name):
    res = {}
    
    columns_to_select = ["id", "gender", variable, groupby]
    
    subset_long = long_df[long_df["group"] == "exp"][columns_to_select].copy()
    subset_wide = subset_long.pivot(index=["id", "gender"], columns=groupby)
    subset_wide.columns = ["_".join(col) for col in subset_wide.columns]
    subset_wide.reset_index(inplace=True)
    
    men = subset_wide[variable + "_man"]
    women = subset_wide[variable + "_woman"]
    n = subset_wide.shape[0]
    paired_difference =  men - women
    mean_men = mean(men)
    mean_women = mean(women)
    res["mean_men"] = mean_men
    res["mean_women"] = mean_women
    
    # Shapiro-Wilk test for normality of the paired difference
    if paired_difference.nunique() > 1:
        _, sw_p = shapiro(paired_difference)
        res["sw_p"] = sw_p
        print("Shapiro-Wilk test for normality for " + variable + " difference of pairs ("+groupby+"): pvalue=" + str(sw_p))
        if sw_p < 0.05:
            print("Data does not follow a normal distribution")
        else:
            print("Data follows a normal distribution")
    else:
        print("paired difference for " + variable + " has zero range")
    
    # Paired two-sided t-test
    _, ttest_p = ttest_rel(men,women)
    res["ttest_p"] = ttest_p
    print("\nParametric two sided paired t-test for " + variable + " ("+groupby+"): pvalue=" + str(ttest_p))

    if ttest_p < 0.05:
        print("The difference between the means is statistically significant")
    else:
        print("The difference between the means is not statistically significant")

    # Cohen's d for paired data
    mean_difference = np.mean(men - women)
    std_difference = np.std(men - women, ddof=1)  # ddof=1 for sample standard deviation
    cohens_d = mean_difference / std_difference
    res["cohens_d"] = cohens_d
    print("\nCohen's d for paired data for " + variable + " ("+groupby+"): " + str(cohens_d))
    if cohens_d > 0.8:
        print("Cohen's d is large")
    elif cohens_d > 0.5:
        print("Cohen's d is moderate")
    elif cohens_d > 0.2:
        print("Cohen's d is small")
    else:
        print("Cohen's d is negligible")
    
    # One-way repeated measures ANOVA
    aov = pg.rm_anova(data=subset_wide)
    anova_p = aov.iloc[0]["p-unc"]
    print("\nParametric one-way repeated measures ANOVA for "+variable+" ~ "+groupby+": pvalue="+str(anova_p))
    res["anova_p"] = anova_p
    
    if anova_p < 0.05:
        print("The difference between the means is statistically significant")
    else:
        print("The difference between the means is not statistically significant")

    # Non-parametric two-sided paired Wilcoxon test
    _, wilcoxon_p = wilcoxon(women, men, alternative="two-sided")
    res["wilcoxon_p"] = wilcoxon_p
    print("\nNon-parametric two-sided paired Wilcoxon test for " + variable + " ("+groupby+"): pvalue=" + str(wilcoxon_p))
    if wilcoxon_p < 0.05:
        print("The difference is statistically significant")
    else:
        print("The difference is not statistically significant")
    
    z_stat = norm.ppf(wilcoxon_p/2)

    # Calculate effect size
    r = abs(z_stat/sqrt(n))
    res["wilcoxon_r"] = r
    
    print("\nWilcoxon effect size: " + str(r))
    if r > 0.5:
        print("Wilcoxon effect size is large")
    elif r > 0.3:
        print("Wilcoxon effect size is moderate")
    elif r > 0.1:
        print("Wilcoxon effect size is small")
    else:
        print("Wilcoxon effect size is negligible")
    
    # Two-way mixed-model ANOVA
    aov = pg.mixed_anova(data=subset_long, dv=variable, within=groupby, between="gender", subject="id")
    print("\nTwo-Way Mixed model ANOVA")
    print(aov)
    res["aov"] = aov.replace({np.nan: None}).to_dict()
    
    # Plotting
    colors = {"men": "#fd4659", "women": "#33b864"}
    sns.set_style("whitegrid")
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))

    # Density plot
    sns.kdeplot(men, fill=True, color=colors.get("men"), label="men " + groupby, ax=axs[0], bw_adjust=0.7)
    sns.kdeplot(women, fill=True, color=colors.get("women"), label="women " + groupby, ax=axs[0], bw_adjust=0.7)
    
    axs[0].axvline(mean_men, color=colors.get("men"), linestyle="--", label="men " + groupby + " mean")
    axs[0].axvline(mean_women, color=colors.get("women"), linestyle="--", label="women " + groupby + " mean")

    axs[0].grid(True)
    axs[0].set_xlim(0)
    axs[0].set_title(variable + " ~ "+groupby)
    axs[0].set_xlabel(variable)
    axs[0].legend()

    # Boxplot
    df = pd.DataFrame({"men": men, "women": women})
    sns.boxplot(data=df, ax=axs[1], palette=colors, showmeans=True, meanprops={"marker":"o","markerfacecolor":"black", "markeredgecolor":"black", "markersize":"7"})
    axs[1].set_title(variable + " ~ "+groupby)
    axs[1].set_ylabel(variable)
    axs[1].set_xlabel(groupby)

    # Save plot
    plt.tight_layout()
    plt.savefig("analysis/" + session_name + "/plots/within/" + groupby + "/" + variable + ".png")
    res["plot"] = "/analysis/" + session_name + "/plots/within/" + groupby + "/" + variable + ".png"
    
    return res

def analyzeCpsBetween(variable, cps_df, session_name):
    res = {}
    columns_to_select = ["id","group",variable]

    subset_cps = cps_df[columns_to_select].copy()
    control_group = subset_cps[subset_cps["group"]=="ctrl"][variable]
    experimental_group = subset_cps[subset_cps["group"]=="exp"][variable]

    mean_c = mean(control_group)
    mean_e = mean(experimental_group)

    res["mean_control"] = mean_c
    res["mean_experimental"] = mean_e

    # Shapiro-Wilk test for normality in control group for variable
    if control_group.nunique() > 1:
        _, sw_p_control = shapiro(control_group)
        res["sw_p_control"] = sw_p_control
        print("Shapiro-Wilk test for normality in control group for " + variable + ": " + str(sw_p_control))
        if sw_p_control < 0.05:
            print("Control group for " + variable + " does not follow a normal distribution")
        else:
            print("Control group for " + variable + " follows a normal distribution")
    else:
        print("Control group for " + variable + " has zero range")

    # Shapiro-Wilk test for normality in experimental group for variable
    if experimental_group.nunique() > 1:
        _, sw_p_experimental = shapiro(experimental_group)
        res["sw_p_experimental"] = sw_p_experimental
        print("Shapiro-Wilk test for normality in experimental group for " + variable + ": " + str(sw_p_experimental))
        if sw_p_experimental < 0.05:
            print("Experimental group for " + variable + " does not follow a normal distribution")
        else:
            print("Experimental group for " + variable + " follows a normal distribution")
    else:
        print("Experimental group for " + variable + " has zero range")

    # Unpaired two-tailed t-test for equality of means
    _, ttest_p = ttest_ind(control_group, experimental_group, equal_var=False, alternative="two-sided")
    res["ttest_p"] = ttest_p
    print("\nParametric one-tailed (ctrl < exp) unpaired t-test for " + variable + ": pvalue=" + str(ttest_p))

    if ttest_p < 0.05:
        print("The difference between the means is statistically significant")
    else:
        print("The difference between the means is not statistically significant")

    # One-way ANOVA test for score between groups
    aov = pg.anova(data=subset_cps, dv=variable, between="group")
    anova_p = aov.iloc[0]["p-unc"]
    res["anova_p"] = anova_p
    print("\nParametric one-way ANOVA for "+variable+" ~ group: pvalue="+str(anova_p))

    if anova_p < 0.05:
        print("The difference between the means is statistically significant")
    else:
        print("The difference between the means is not statistically significant")

    # Non-parametric unpaired Mann-Whitney U two-sided
    _, mwu_p = mannwhitneyu(control_group, experimental_group, alternative="two-sided")
    res["mwu_p"] = mwu_p
    print("\nNon-parametric two-sided unpaired Mann-Whitney U test for " + variable + ": pvalue=" + str(mwu_p))

    if mwu_p < 0.05:
        print("The difference is statistically significant")
    else:
        print("The difference is not statistically significant")

    # Ploting
    colors = {"ctrl": "#fd4659", "exp": "#33b864"}
    sns.set_style("whitegrid")
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))

    # Density plot
    sns.kdeplot(control_group, fill=True, color=colors.get("ctrl"), label="control", ax=axs[0], bw_adjust=0.7)
    sns.kdeplot(experimental_group, fill=True, color=colors.get("exp"), label="experimental", ax=axs[0], bw_adjust=0.7)

    axs[0].axvline(mean_c, color=colors.get("ctrl"), linestyle="--", label="control mean")
    axs[0].axvline(mean_e, color=colors.get("exp"), linestyle="--", label="experimental mean")

    axs[0].grid(True)
    axs[0].set_xlim(0)
    axs[0].set_title("Compared partners' skills "+variable)
    axs[0].set_xlabel(variable)
    axs[0].legend()

    # Boxplot
    df = pd.DataFrame({"ctrl": control_group, "exp": experimental_group})
    sns.boxplot(data=df, ax=axs[1], palette=colors, showmeans=True, meanprops={"marker":"o","markerfacecolor":"black", "markeredgecolor":"black", "markersize":"7"})
    axs[1].set_title("Compared partners' skills "+variable)
    axs[1].set_ylabel(variable)
    axs[1].set_xlabel("group")

    # Save plot
    plt.tight_layout()
    plt.savefig("analysis/" + session_name + "/plots/cps_between/" + variable + ".png")
    res["plot"] = "/analysis/" + session_name + "/plots/cps_between/"+ variable + ".png"

    return res

def analyzeCpsWithin(variable, cps_df, session_name):
    res = {}
    columns_to_select = ["id","gender", variable]
    
    subset_cps = cps_df[cps_df["group"]=="exp"][columns_to_select].copy()
    men = subset_cps[subset_cps["gender"]=="man"][variable]
    women = subset_cps[subset_cps["gender"]=="woman"][variable]
    
    mean_men = mean(men)
    mean_women = mean(women)
    res["mean_men"] = mean_men
    res["mean_women"] = mean_women
    
    # Men group Shapiro-Wilk test for normality
    if men.nunique() > 1:
        _, sw_p_men = shapiro(men)
        res["sw_p_men"] = sw_p_men
        print("Shapiro-Wilk test for normality in men group for " + variable + ": " + str(sw_p_men))
        if sw_p_men < 0.05:
            print("Men group for " + variable + " does not follow a normal distribution")
        else:
            print("Men group for " + variable + " follows a normal distribution")
    else:
        print("Men group for " + variable + " has zero range")
    
    # Women group Shapiro-Wilk test for normality
    if women.nunique() > 1:
        _, sw_p_women = shapiro(women)
        res["sw_p_women"] = sw_p_women
        print("Shapiro-Wilk test for normality in women group for " + variable + ": " + str(sw_p_women))
        if sw_p_women < 0.05:
            print("Women group for " + variable + " does not follow a normal distribution")
        else:
            print("Women group for " + variable + " follows a normal distribution")
    else:
        print("Women group for " + variable + " has zero range")
    
    # Unpaired two-tailed t-test for equality of means
    _, ttest_p = ttest_ind(men, women, equal_var=False, alternative="two-sided")
    res["ttest_p"] = ttest_p
    print("\nParametric one-tailed (ctrl < exp) unpaired t-test for " + variable + ": pvalue=" + str(ttest_p))

    if ttest_p < 0.05:
        print("The difference between the means is statistically significant")
    else:
        print("The difference between the means is not statistically significant")
    
    # One-way ANOVA test for score between gender
    aov = pg.anova(data=subset_cps, dv=variable, between="gender")
    anova_p = aov.iloc[0]["p-unc"]
    res["anova_p"] = anova_p
    print("\nParametric one-way ANOVA for "+variable+" ~ gender: pvalue="+str(anova_p))
    
    if anova_p < 0.05:
        print("The difference between the means is statistically significant")
    else:
        print("The difference between the means is not statistically significant")
    
    # Non-parametric unpaired Mann-Whitney U two-sided
    _, mwu_p = mannwhitneyu(men, women, alternative="two-sided")
    res["mwu_p"] = mwu_p
    print("\nNon-parametric two-sided unpaired Mann-Whitney U test for " + variable + ": pvalue=" + str(mwu_p))

    if mwu_p < 0.05:
        print("The difference is statistically significant")
    else:
        print("The difference is not statistically significant")
    
    # Ploting
    colors = {"men": "#fd4659", "women": "#33b864"}
    sns.set_style("whitegrid")
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))

    # Density plot
    sns.kdeplot(men, fill=True, color=colors.get("men"), label="men", ax=axs[0], bw_adjust=0.7)
    sns.kdeplot(women, fill=True, color=colors.get("women"), label="women", ax=axs[0], bw_adjust=0.7)
    
    axs[0].axvline(mean_men, color=colors.get("men"), linestyle="--", label="men mean")
    axs[0].axvline(mean_women, color=colors.get("women"), linestyle="--", label="women mean")

    axs[0].grid(True)
    axs[0].set_xlim(0)
    axs[0].set_title("Compared partners' skills "+variable)
    axs[0].set_xlabel(variable)
    axs[0].legend()

    # Boxplot
    df = pd.DataFrame({"men": men, "women": women})
    sns.boxplot(data=df, ax=axs[1], palette=colors, showmeans=True, meanprops={"marker":"o","markerfacecolor":"black", "markeredgecolor":"black", "markersize":"7"})
    axs[1].set_title("Compared partners' skills "+variable)
    axs[1].set_ylabel(variable)
    axs[1].set_xlabel("gender")

    # Save plot
    plt.tight_layout()
    plt.savefig("analysis/" + session_name + "/plots/cps_within/" + variable + ".png")
    res["plot"] = "/analysis/" + session_name + "/plots/cps_within/"+ variable + ".png"
    
    return res