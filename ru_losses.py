import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import requests, json


def path2df(path: str) -> pd.DataFrame:
    """
    Takes a path in input and returns a dataframe. To date, .csv and .json format allowed.
    """
    try:
        if path[-3:] == 'csv':
            df = pd.read_csv(path)
        elif path[-4:] == 'json':
            df = pd.DataFrame(requests.get(path).json())
        else:
            raise Exception("Format not yet implemented")
    except ValueError:
        print("Path is incorrect")
    return df


class RULosses:
    """
    
    Args
    ----
    file_path    : url with data
    corrige_path : url with corrige data
    autoload     : True to automatically load data in member .df
    """
    
    def __init__(self, file_path: str, corrige_path: str='', autoload: bool=False):
        self.file_path = file_path
        self.corrige_path = None if corrige_path == '' else corrige_path
        if autoload: self.import_data()
    
    
    def import_data(self, keep_losses_direction: bool=False):
        # russian losses
        df = path2df(self.file_path)
    
        # data corrige import and apply
        df_corrected = df.copy()
        if self.corrige_path is not None:
            df_corrige      = path2df(self.corrige_path)
            corrige_cols    = df_corrige.columns[2:] # exclude "date" and "day" columns
            subdf_corrected = df_corrected.loc[df.day.isin(df_corrige.day), corrige_cols]
            subdf_corrige   = df_corrige.loc[:, corrige_cols].set_index(subdf_corrected.index)
            df_corrected.loc[subdf_corrected.index, subdf_corrected.columns] = subdf_corrected.add(subdf_corrige)
            assert sum(df_corrected.index.values - df.index.values) == 0 # sanity check 
    
        if not keep_losses_direction:
            df_corrected = df_corrected.drop(columns="greatest losses direction")
   
        self.df = df_corrected
    
        print("Last date available: {}".format(self.df.date.to_numpy()[-1]))


    def resample(self, period: str='D'):
        """
        to transform cumulative into daily, weekly or other period

        Args
        ----
        period : daily ='D', weekly ='W', monthly ='M', do nothing =''
        """
        df = self.df.copy()
        df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d") # convert date column to proper datetime type
        if period == '': # no resampling
            df.loc[:,~df.columns.isin(["date", "day"])] = df.loc[:,~df.columns.isin(["date", "day"])].fillna(0).astype(int) # replace NaNs with (int) 0s
        else:
            df.loc[:,~df.columns.isin(["date", "day"])] = df.loc[:,~df.columns.isin(["date", "day"])].diff().fillna(0).astype(int) # convert to daily and replace NaNs with (int) 0s
            df["day"] = df["day"] - 1 # correct shift of day
            resA_df   = df.loc[:, ["date", "day"]].resample(period, label='right', on="date").max() # for "day" use max i.e. the day period ends
            resB_df   = df.loc[:, df.columns != "day"].resample(period, label='right', on="date").sum() # for equipment, use accumul per period
            df        = pd.merge(resA_df, resB_df, on="date", how='inner').reset_index() # merge "day" and other columns

        self.period = period
        self.df     = df


    def inspect(self):
        """
        print a diagnostic table with useful info
        """
        print(pd.DataFrame({
                    "features": self.df.dtypes.index,
                    "dtypes": self.df.dtypes.values, 
                    "N. of elems": self.df.size*np.ones(shape=(self.df.dtypes.size,), dtype=int),
                    "NULL perc.": 100*self.df.isnull().mean().values, 
                    "most freq. val": self.df.mode().iloc[0].values
                    }).to_string())

    
    def cond_plot(self, columns: list, events: list, figsize: tuple=(8,6), **kwargs) -> tuple:
        """
        plot data conditionally resampled on multiple events

        x axis is the temporal unit from the event
        y axis is the number of losses per unit of time (that of x axis)
        one subplot per selected column
        
        Args
        ----
        columns : df columns to be plotted on each subplot (stacked vertically)
        events  : dates to set zero of resempling
        figsize : whole figure size
        kwargs  : of pyplot
        """
        # prepare data: dataframe per each event in a dictionary
        df      = self.df.copy()    
        df_dict = {events[j]: None for j in range(len(events))}
        for j in range(len(events)):
            if j != len(events)-1:
                df_dict[events[j]] = df.loc[((df["date"]>=events[j]) & (df["date"]<events[j+1])),columns].reset_index()
            else:
                df_dict[events[j]] = df.loc[(df["date"]>=events[j]),columns].reset_index()

        # produce plot, one subplot per column
        fig, axs = plt.subplots(nrows=len(columns), ncols=1, figsize=figsize)
        if len(columns) == 1: # if no more than 1 subplots axs would be not subscriptable
            axs = [axs]
        for cc in range(len(columns)):
            for event in events:
                df_dict[event][columns[cc]].plot(ax=axs[cc], **kwargs)
            axs[cc].set_ylabel("N. of pieces / " + self.period)
            axs[cc].set_xlabel((self.period if self.period!='' else "Day") + "s from the event")
            axs[cc].title.set_text("Losses of " + columns[cc])
            axs[cc].legend(events if "legend" not in kwargs.keys() else kwargs["legend"], loc="upper right")
        plt.subplots_adjust(hspace=0.5) # give room between stacked subplots
        plt.show() 

        return fig, axs




if __name__ == '__main__':
    loss = RULosses(file_path="https://raw.githubusercontent.com/PetroIvaniuk/2022-Ukraine-Russia-War-Dataset/main/data/russia_losses_equipment.json",
                    corrige_path="", autoload=True)
    
    loss.inspect()
    loss.resample(period='3D')

    loss.cond_plot(
                   columns=["field artillery","special equipment","anti-aircraft warfare","tank"],
                   events=['2022-02-24','2022-08-01','2023-05-01'],
                   legend=['Invasion Feb 2022', 'Kherson+Kharkiv Ago 2022', 'Zaporizhzhia+Donetsk Jun 2023'],
                   figsize=(8,12), ls='-'
                  )
