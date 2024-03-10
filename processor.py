import pandas as pd
import os
import numpy as np
from scipy.stats import chi2_contingency

# create new names for the columns
pp_names = ["pp" + str(i) for i in range(1, 5)]
pptc_names = ["pptc" + str(i) for i in range(1, 5)]
cps_names = ["cps" + str(i) for i in range(1, 6)]
ppgender_names = ["ppgender" + str(i) for i in range(1, 3)]

def process_form1(df):
    # drop the first 7 columns
    df = df.drop(df.columns[0:7], axis=1)

    # drop all empty columns
    df = df.loc[:, df.any()]

    # set the column names
    df.columns = ["id"]+pp_names+pptc_names+["ppna"]

    # convert all columns except the first (id) and last (ppna) to numeric
    df[df.columns[1:-1]] = df[df.columns[1:-1]].apply(pd.to_numeric, errors='coerce')

    

    # add column with the number of "\\+" in the ppna column called ppa
    df["ppa"] = df["ppna"].str.count("\\+")
    df["ppn"] = df["ppna"].str.count("\\-")

    # remove ppna column
    df = df.drop(columns=["ppna"])

    # column for the mean of the pp
    df.insert(5, "pp", df[pp_names].mean(axis=1))

    # column for the mean of the pptc
    df.insert(10, "pptc", df[pptc_names].mean(axis=1))
    df.to_html("form1.html")

    return df

def process_form2(df):
    # drop the first 7 columns
    df = df.drop(df.columns[0:7], axis=1)

    # drop all empty columns
    df = df.loc[:, df.any()]

    # change the column names
    df.columns = ["id"]+pp_names+pptc_names+["ppna"]+cps_names+["av"]+ppgender_names

    # convert all columns except 0, 9, 
    df[df.columns[1:9]] = df[df.columns[1:9]].apply(pd.to_numeric, errors='coerce')
    df[df.columns[10:15]] = df[df.columns[10:15]].apply(pd.to_numeric, errors='coerce')

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
                                                    np.where(df["av"] == "idr", "idr",np.nan)))))
    
    df["ppgender2"] = np.where(df["ppgender2"].notnull() & df["ppgender2"].str.upper().str.match(r".*(AVATAR A).*"), "man",
                            np.where(df["ppgender2"].notnull() & df["ppgender2"].str.upper().str.match(r".*(AVATAR B).*"), "woman",
                                    np.where(df["ppgender2"].notnull() & df["ppgender2"].str.lower().str.match(r".*(remember|recuerdo).*"), "idr",
                                            np.where(df["av"] == "no", "none",
                                                    np.where(df["av"] == "idr", "idr",np.nan)))))

    df.to_html("form2.html")
    return df