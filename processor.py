import pandas as pd
import numpy as np


def process_form1(df):
    # create new names for the columns
    pp_names = ["pp" + str(i) for i in range(1, 5)]
    pptc_names = ["pptc" + str(i) for i in range(1, 5)]

    # drop the first column
    df = df.drop(df.columns[0], axis=1)

    # drop all empty columns
    df = df.loc[:, df.any()]

    # set the column names
    df.columns = ["id"]+pp_names+pptc_names+["ppna"]

    # convert all columns except the first (id) and last (ppna) to numeric
    df[df.columns[1:-1]] = df[df.columns[1:-1]
                              ].apply(pd.to_numeric, errors='coerce')
    
    # convert first column to string
    df["id"] = df["id"].astype(str)

    # add column with the number of "\\+" in the ppna column called ppa
    df["ppa"] = df["ppna"].str.count("\\+")
    df["ppn"] = df["ppna"].str.count("\\-")

    # remove ppna column
    df = df.drop(columns=["ppna"])

    # column for the mean of the pp
    df.insert(5, "pp", df[pp_names].mean(axis=1))

    # column for the mean of the pptc
    df.insert(10, "pptc", df[pptc_names].mean(axis=1))

    return df


def process_form2(df):

    # create new names for the columns
    pp_names = ["pp" + str(i) for i in range(1, 5)]
    pptc_names = ["pptc" + str(i) for i in range(1, 5)]
    cps_names = ["cps" + str(i) for i in range(1, 6)]
    ppgender_names = ["ppgender" + str(i) for i in range(1, 3)]

    # drop the first column
    df = df.drop(df.columns[0], axis=1)

    # drop all empty columns
    df = df.loc[:, df.any()]

    # change the column names
    df.columns = ["id"]+pp_names+pptc_names + \
        ["ppna"]+cps_names+["av"]+ppgender_names

    # convert all columns except 0, 9,
    df[df.columns[1:9]] = df[df.columns[1:9]].apply(
        pd.to_numeric, errors='coerce')
    df[df.columns[10:15]] = df[df.columns[10:15]].apply(
        pd.to_numeric, errors='coerce')
    
    # convert first column to string
    df["id"] = df["id"].astype(str)

    # column for the mean of the pp and pptc
    df.insert(5, "pp", df[pp_names].mean(axis=1))
    df.insert(10, "pptc", df[pptc_names].mean(axis=1))

    # column for ppa and ppn
    df.insert(12, "ppa", df["ppna"].str.count("\\+"))
    df.insert(13, "ppn", df["ppna"].str.count("\\-"))
    df = df.drop(columns=["ppna"])

    # av column, yes, no, idr
    df["av"] = np.where(df["av"].str.match(r".*(Yes, |Sí, ).*"), "yes",
                        np.where(df["av"].str.match(r".*No, .*"), "no",
                                 np.where(df["av"].str.match(r".*(remember|recuerdo).*"), "idr", np.nan)))

    # ppgender columns 1 and 2 none, idr, man, woman
    df["ppgender1"] = np.where(df["ppgender1"].notnull() & df["ppgender1"].str.upper().str.match(r".*(AVATAR A).*"), "man",
                               np.where(df["ppgender1"].notnull() & df["ppgender1"].str.upper().str.match(r".*(AVATAR B).*"), "woman",
                                        np.where(df["ppgender1"].notnull() & df["ppgender1"].str.lower().str.match(r".*(remember|recuerdo).*"), "idr",
                                                 np.where(df["av"] == "no", "none",
                                                          np.where(df["av"] == "idr", "idr", np.nan)))))

    df["ppgender2"] = np.where(df["ppgender2"].notnull() & df["ppgender2"].str.upper().str.match(r".*(AVATAR A).*"), "man",
                               np.where(df["ppgender2"].notnull() & df["ppgender2"].str.upper().str.match(r".*(AVATAR B).*"), "woman",
                                        np.where(df["ppgender2"].notnull() & df["ppgender2"].str.lower().str.match(r".*(remember|recuerdo).*"), "idr",
                                                 np.where(df["av"] == "no", "none",
                                                          np.where(df["av"] == "idr", "idr", np.nan)))))

    return df

def filter_ids(form1, form2, metrics, tagging):
    # take only data from users that have completed both forms and appear in the metrics files
    valid_ids = set(form1["id"]).intersection(set(form2["id"]).intersection(set(metrics["id"])).intersection(set(metrics["partnerid"])))

    # filter metrics file by valid ids
    metrics = metrics[metrics["id"].isin(valid_ids)]

    # new dataframe with id, group, partnerid, group_partner to see if there are any pairs that are in the same group (experimental or control)
    valid_pairs = metrics[["time","id", "group", "partnerid"]]
    valid_pairs = pd.merge(valid_pairs, valid_pairs[["time","id","group"]], left_on=["time","partnerid"], right_on=["time","id"], suffixes=("", "_partner"))[["time","id", "group", "partnerid", "group_partner"]]

    valid_pairs_t1 = valid_pairs[valid_pairs["time"] == "t1"]
    valid_pairs_t2 = valid_pairs[valid_pairs["time"] == "t2"]

    valid_pairs_t1 = valid_pairs_t1[valid_pairs_t1["group"] != valid_pairs_t1["group_partner"]]
    valid_pairs_t2 = valid_pairs_t2[valid_pairs_t2["group"] != valid_pairs_t2["group_partner"]]

    valid_ids = set(valid_pairs_t1["id"]).intersection(set(valid_pairs_t2["id"]))

    # now that we have all valid ids filtered from metrics and form files, we need to filter with the tagging file
    valid_ids = set(valid_ids).intersection(set(tagging["id"]))

    # filter all files with real valid ids
    metrics = metrics[metrics["id"].isin(valid_ids)]
    form1 = form1[form1["id"].isin(valid_ids)]
    form2 = form2[form2["id"].isin(valid_ids)]
    tagging = tagging[tagging["id"].isin(valid_ids)]
    
    return form1, form2, metrics, tagging

def join_files(form1, form2, metrics, tagging):
    
    cps_names = ["cps" + str(i) for i in range(1, 6)]
    
    # ATTRIBUTES AT T1
    metrics_t1 = metrics[metrics["time"] == "t1"]
    tagging_t1 = tagging[tagging["time"] == "t1"]

    # get ppgender_t1 and ppgender_t2 from form2
    ppgender_t1 = form2[["id", "ppgender1"]]

    # add ppgender_t1 to metrics_t1
    metrics_t1 = pd.merge(metrics_t1, ppgender_t1, on="id")
    move = metrics_t1.pop("ppgender1")
    metrics_t1.insert(4, "ppgender", move)


    # add questionnaire 1 to metrics_t1
    metrics_t1 = metrics_t1.join(form1.set_index("id"), on="id", how="inner")

    # add tagging_t1 to metrics_t1
    metrics_t1 = pd.merge(metrics_t1, tagging_t1, on=["id", "time"])

    # ATTRIBUTES AT T2
    metrics_t2 = metrics[metrics["time"] == "t2"]
    tagging_t2 = tagging[tagging["time"] == "t2"]

    # get ppgender_t2 from form2
    ppgender_t2 = form2[["id", "ppgender2"]]
    metrics_t2 = pd.merge(metrics_t2, ppgender_t2, on="id")
    move = metrics_t2.pop("ppgender2")
    metrics_t2.insert(4, "ppgender", move)

    # add questionnaire 2 to metrics_t2 excluding cps variables, av, ppgender1, ppgender2.
    metrics_t2 = pd.merge(metrics_t2, form2.drop(columns=cps_names+["av", "ppgender1", "ppgender2"]), on="id")

    # add tagging_t2 to metrics_t2
    metrics_t2 = pd.merge(metrics_t2, tagging_t2, on=["id", "time"])

    # create long format from metrics_t1 and metrics_t2
    long_df = pd.concat([metrics_t1, metrics_t2], ignore_index=True)
    
    return long_df

def filter_gender_perception(long_df):
    # Filter long_df excluding control group subjects whose ppgender different from "none" or "idr"
    excluded_ctrl = long_df[(long_df["group"] == "ctrl") & (long_df["ppgender"] != "none") & (long_df["ppgender"] != "idr")]
    excluded_ctrl_ids = excluded_ctrl["id"].unique()
    long_df = long_df[~long_df["id"].isin(excluded_ctrl_ids)]

    # Filter long_df excluding experimental group subjects who percieved the induced gender at t1 and t2
    excluded_exp = long_df[(long_df["group"] == "exp") & (long_df["ppgender"] != long_df["ipgender"])]
    excluded_exp_ids = excluded_exp["id"].unique()
    long_df = long_df[~long_df["id"].isin(excluded_exp_ids)]
    
    return long_df

def create_cps_df(long_df, form2):
    cps_names = ["cps" + str(i) for i in range(1, 6)]
    # get cps variables from form2 -> taking in account that if the perceived gender in t2 is man, we have to reverse the cps
    cps_df = long_df[long_df["time"] == "t2"][["id", "group", "gender", "ipgender"]]
    cps_df = pd.merge(cps_df, form2[["id"]+cps_names], on="id")

    # If the induced partner gender at t2 is "man", reverse the score (max score - score) for all the CPS variables
    cps_df[cps_names] = np.where(cps_df[["ipgender"]] == "man", 10 - cps_df[cps_names], cps_df[cps_names])

    # cps average
    cps_df["cps"] = cps_df[cps_names].mean(axis=1)
    
    return cps_df

def create_wide_df(long_df):
    # Create wide format
    wide_df = long_df.pivot(index=["id", "group", "gender", "partnerid"], columns="time")
    wide_df.columns = ["_".join(col) for col in wide_df.columns]
    wide_df = wide_df.reset_index()
    
    return wide_df