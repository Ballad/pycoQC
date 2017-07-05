# -*- coding: utf-8 -*-

"""       
  ___              ___   ___ 
 | _ \_  _ __ ___ / _ \ / __|
 |  _/ || / _/ _ \ (_) | (__ 
 |_|  \_, \__\___/\__\_\\___|
      |__/      
                                __   __     ___ 
 /\  _| _. _ _   |   _ _  _ _    _) /  \ /|   / 
/--\(_|| |(-| )  |__(-(_)(-|    /__ \__/  |  /  
                      _/                        
"""

# Standard library imports
from sys import exit as sysexit
from os import access, R_OK
from collections import OrderedDict
from pkg_resources import Requirement, resource_filename

# Local reports
try:
    from pycoQC.pycoQC_fun import print, help, get_sample_file
except ImportError:
    from pycoQC_fun import print, help, get_sample_file

# Third party imports
try:
    import numpy as np
    import pylab as pl
    import pandas as pd
    import seaborn as sns
    get_ipython()
    from IPython.core.display import display
    
except (NameError, ImportError) as E:
    print (E)
    print ("A third party package is missing. Please verify your dependencies")
    sysexit()

##~~~~~~~ SAMPLE FILE ~~~~~~~#

sequencing_summary_file = get_sample_file("pycoQC",'pycoQC/data/sequencing_summary.txt')
sequencing_summary_file_1dsq = get_sample_file("pycoQC",'pycoQC/data/sequencing_1dsq_summary.txt')


##~~~~~~~ MAIN CLASS ~~~~~~~#
class pycoQC():

    #~~~~~~~FUNDAMENTAL METHODS~~~~~~~#    
    def __init__ (self, seq_summary_file, runid=None, filter_zero_len=False, verbose=False):
        """
        Parse Albacore sequencing_summary.txt file and clean-up the data
        * seq_summary_file
            Path to the sequencing_summary.txt generated by Albacore
        * runid
            If you want a specific runid to be analysed. By default it will analyse all the read in the file irrespective of their runid 
            [Default None]
        * filter_zero_len
            If True, zero length reads will be filtered out. [Default False]
        * verbose
            print additional informations. [Default False]
        """
        self.verbose=verbose
        
        # Import the summary file in a dataframe
        if verbose: print("Importing data", bold=True)
        self.seq_summary_file = seq_summary_file
        self.df = pd.read_csv(seq_summary_file, sep ="\t")
        self.df.dropna(inplace=True)
        if verbose: print("\t{} reads found in initial file".format(len(self.df)))
        
        # Verify the presence of the columns required for pycoQC
        if verbose: print("Checking fields in dataframe", bold=True)
        try:
            for colname in ['run_id', 'channel', 'start_time', 'duration', 'num_events','sequence_length_template', 'mean_qscore_template']:
                assert colname in self.df.columns
            self.run_type = '1D'

        except AssertionError:
            print("Column {} not found in the provided sequence_summary file, "
                  "trying 2D or 1D^2 column formats...".format(colname))

            for colname in ['run_id', 'channel', 'start_time', 'sequence_length_2d', 'mean_qscore_2d']:
                assert colname in self.df.columns, "Column {} not found in the provided sequence_summary file".format(colname)
            
            # interpolate and rename columns to make compatible with other code

            # provide an estimate of duration, assuming 450 bases / second
            self.df['duration'] = self.df['sequence_length_2d'] / 450

            # provide an estimate of num events, assuming 1.8 events / base
            self.df['num_events'] = self.df['sequence_length_2d'] * 1.8

            # add renamed columns to match 1D expectations
            self.df['sequence_length_template'] = self.df['sequence_length_2d']
            self.df['mean_qscore_template'] = self.df['mean_qscore_2d']

            self.run_type = '2D'

        if verbose: print("\tAll valid for run type {}".format(self.run_type))
        
        # Filter out zero length if required
        if filter_zero_len:
            if verbose: print ("Filter out zero length reads", bold = True)
            l = len(self.df)
            self.df = self.df[(self.df['sequence_length_template'] > 0)]
            self.zero_len_reads = l-len(self.df)
            if verbose: print ("\t{} reads discarded".format(self.zero_len_reads))

        # Select Runid if required
        if runid:
            if verbose: print ("Selecting reads with Run_ID {}".format(runid), bold=True)
            l = len(self.df)
            self.df = self.df[(self.df["run_id"] == runid)]
            if verbose: print ("\t{} reads discarded".format(l-len(self.df)))
        
        # Reads per runid
        if verbose: print("Counting reads per runid", bold=True)
        self.runid_counts = self.df['run_id'].value_counts(sort=True).to_frame(name="Counts")
        if verbose: print("\tFound {} runid".format(len(self.runid_counts)))
            
        # Extract the runid data from the overall dataframe
        if verbose: print("Final data cleanup", bold=True)
        self.df = self.df.reset_index(drop=True)
        self.df.set_index("read_id", inplace=True)
        self.total_reads = len(self.df)
        if verbose: print("\t{} Total valid reads found".format(self.total_reads))
        
    
    def __str__(self):
        """readable description of the object"""
        msg = "{} instance\n".format(self.__class__.__name__)
        msg+= "\tParameters list\n"
        
        # list all values in object dict in alphabetical order
        for k,v in OrderedDict(sorted(self.__dict__.items(), key=lambda t: t[0])).items():
            if k != "df":
                msg+="\t{}\t{}\n".format(k, v)
        return (msg)

    #~~~~~~~PUBLIC METHODS~~~~~~~#
    
    def overview (self):
        """
        Generate a quick overview of the data (tables + plots)
        """        
        print ("General counts", bold=True)
        df = pd.DataFrame(columns=["Count"])
        df.loc["Reads", "Count"] = len(self.df)
        df.loc["Bases", "Count"] = self.df["sequence_length_template"].sum()
        df.loc["Events", "Count"] = self.df["num_events"].sum()
        df.loc["Active Channels", "Count"] = self.df["channel"].nunique()
        df.loc["Run Duration (h)", "Count"] = ((self.df["start_time"]+self.df["duration"]).max() - self.df["start_time"].min())/3600
        display(df)
        
        print ("Read count per Run ID", bold=True)
        display(self.runid_counts)
        
        print ("Distribution of quality scores and read lengths", bold=True)
        df = self.df[['mean_qscore_template', 'sequence_length_template']].describe(percentiles=[0.1,0.25,0.5, 0.75, 0.90])
        df.rename(columns={'mean_qscore_template': 'Quality score distribution', 'sequence_length_template': 'Read length distribution'},
            inplace=True)
        display(df)
        
        fig, (ax1, ax2) = pl.subplots(1, 2, figsize=(12, 6))
        g1 = sns.violinplot(data=self.df['mean_qscore_template'].sample(50000), color="orangered", alpha=0.5, bw=.2, linewidth=1,
            inner="quartile", ax=ax1)
        t = ax1.set_title("Quality score distribution")
        g2 = sns.violinplot(data=self.df['sequence_length_template'].sample(50000), color="orangered", alpha=0.5, bw=.2, cut=1, linewidth=1,
            inner="quartile", ax=ax2)
        t= ax2.set_title("Read length distribution")
    
    def reads_len_bins (self, bins=[-1,0,25,50,100,500,1000,5000,10000,100000,10000000]):
        """
        Count the number of reads per interval of sequence length and return a dataframe
        * bins
            Limits of the intervals as a list 
            [Default [-1,0,25,50,100,500,1000,5000,10000,100000,10000000]]
        """
        df = self.df['sequence_length_template'].groupby(pd.cut(self.df['sequence_length_template'], bins))
        df = df.count().to_frame(name="Count")
        df.index.name="Sequence lenght ranges"
        return df
    
    def reads_qual_bins (self, bins=[-1,0,2,4,6,8,10,12,14,16,18,20,40]):
        """
        Count the number of reads per interval of sequence quality and return a dataframe
        * bins
            Limits of the intervals as a list 
            [Default [-1,0,2,4,6,8,10,12,14,16,18,20,40]]
        """
        df = self.df['mean_qscore_template'].groupby(pd.cut(self.df['mean_qscore_template'], bins))
        df = df.count().to_frame(name="Count")
        df.index.name="Sequence quality ranges"
        return df    
    
    def channels_activity (self, level="reads", figsize=[24,12], cmap="OrRd", alpha=1, robust=True, annot=True, fmt="d", cbar=False,
        **kwargs):
        """
        Plot the activity of channels at read, base or event level. The layout does not represent the physical layout of the flowcell
        * level
            Aggregate channel output results by "reads", "bases" or "events". [Default "reads"]
        * figsize 
            Size of ploting area [Default [24,12]]
        * cmap
            Matplotlib colormap code to color the space [Default "OrRd"]
        * alpha
            Opacity of the area from 0 to 1 [Default 1]
        * robust
            if True the colormap range is computed with robust quantiles instead of the extreme values [Default True]
        * annot
            If True, write the data value in each cell. [Default True]
        * fmt
            String formatting code to use when adding annotations (see matplotlib documentation) [Default "d"]
        * cbar
            Whether to draw a colorbar scale on the right of the graph [Default False]
        => Return
            A matplotlib.axes object for further user customisation (http://matplotlib.org/api/axes_api.html)
        """
        
        # Compute the count per channel
        if level == "reads":
            s = self.df['channel'].value_counts(sort=False)
            title = "Reads per channels"
        if level == "bases":
            s = self.df.groupby("channel").aggregate(np.sum)["sequence_length_template"]
            title = "Bases per channels"
        if level == "events":
            s = self.df.groupby("channel").aggregate(np.sum)["num_events"]
            title = "Events per channels"
            
        # Fill the missing values
        for i in range(1, 512):
            if i not in s.index:
                s.loc[i] = 0

        # Sort by index value 
        s.sort_index(inplace=True)

        # Reshape the series to a 2D frame similar to the Nanopore flowcell grid 
        a = s.values.reshape(16,32)

        # Plot a heatmap like grapd
        fig, ax = pl.subplots(figsize=figsize)
        ax = sns.heatmap(a, ax=ax, annot=annot, fmt=fmt, linewidths=2, cbar=cbar, cmap=cmap, alpha=alpha, robust=robust)
                    
        # Tweak the plot
        t = ax.set_title (title)
        t = ax.set_xticklabels("")
        t = ax.set_yticklabels("")
        
        for text in ax.texts:
            text.set_size(8)
        
        return ax
    
    def reads_qual_distribution (self, figsize=[30,7], hist=True, kde=True, kde_color="black", hist_color="orangered", kde_alpha=0.5,
        hist_alpha=0.5, win_size=0.1, sample=100000, min_qual=None, max_qual=None, min_freq=None, max_freq=None, **kwargs):
        """
        Plot the distribution of mean read quality
        * figsize
            Size of ploting area [Default [30,7]]
        * hist
            If True plot an histogram of distribution [Default True]
        * kde
            If True plot a univariate kernel density estimate [Default True]
        * kde_color / hist_color
            Color map or color codes to use for the 3 plots [Default "black" "orangered"]
        * kde_alpha / hist_alpha
            Opacity of the area from 0 to 1 for the 3 plots [Default 0.5 0.5]
        * win_size
            Size of the bins in quality score ranging from 0 to 40 for the histogram [Default 0.1]
        * sample
            If given, a n number of reads will be randomly selected instead of the entire dataframe [Default 100000]
        * xmin, xmax, ymin, ymax
            Lower and upper limits on x/y axis [Default None]
        * min_qual, max_qual
            Minimal and maximal read quality cut-offs for the plot [Default None]
        * min_freq, max_freq
            Minimal and maximal read frequency cut-offs for the plot [Default None]
        => Return
            A matplotlib.axes object for further user customisation (http://matplotlib.org/api/axes_api.html)
        """
        
        # Select reads
        df = self.df[['mean_qscore_template']]
        if min_qual:
            df = df[(df['mean_qscore_template'] >= min_qual)]
        else:
            min_qual = 0
        if max_qual:
            df = df[(df['mean_qscore_template'] <= max_qual)]
        else:
            max_qual = max(df['mean_qscore_template'])
        if sample and len(df) > sample: 
            df = df.sample(sample)
        
        # Auto correct windows size if too long
        if max_qual-min_qual < win_size:
            win_size = max_qual-min_qual
        
        # Plot
        fig, ax = pl.subplots(figsize=figsize)
        # Plot the kde graph
        if kde:
            sns.kdeplot(df["mean_qscore_template"], ax=ax, color=kde_color, alpha=kde_alpha, shade=not hist, gridsize=500,
                legend=False)
        # Plot a frequency histogram 
        if hist:
            ax = df['mean_qscore_template'].plot.hist(
                bins=np.arange(min_qual, max_qual, win_size), ax=ax, normed=True, color=hist_color, alpha=hist_alpha, histtype='stepfilled')
        
        # Tweak the plot       
        t = ax.set_title ("Mean quality distribution per read")
        t = ax.set_xlabel("Mean PHRED quality Score")
        t = ax.set_ylabel("Read Frequency")
        
        if not min_freq:
            min_freq = 0
        if not max_freq:
            max_freq = ax.get_ylim()[1]
            
        t = ax.set_xlim([min_qual, max_qual])
        t = ax.set_ylim([min_freq, max_freq])
        
        return ax
        
    def reads_len_distribution (self, figsize=[30,7], hist=True, kde=True, kde_color="black", hist_color="orangered", kde_alpha=0.5,
        hist_alpha=0.5, win_size=250, sample=100000, min_len=None, max_len=None, min_freq=None, max_freq=None, **kwargs):
            
        """
        Plot the distribution of read length in base pairs
        * figsize
            Size of ploting area [Default [30,7]]
        * hist
            If True plot an histogram of distribution [Default True]
        * kde
            If True plot a univariate kernel density estimate [Default True]
        * kde_color / hist_color
            Color map or color codes to use for the 3 plots [Default "black" "orangered"]
        * kde_alpha / hist_alpha
            Opacity of the area from 0 to 1 for the 3 plots [Default 0.5 0.5]
        * win_size
            Size of the bins in base pairs for the histogram [Default 250]
        * sample
            If given, a n number of reads will be randomly selected instead of the entire dataframe [Default 100000]
        * min_len, max_len
            Minimal and maximal read length cut-offs for the plot [Default None]
        * min_freq, max_freq
            Minimal and maximal read frequency cut-offs for the plot [Default None]
        => Return
            A matplotlib.axes object for further user customisation (http://matplotlib.org/api/axes_api.html)
        """
        
        # Select reads
        df = self.df[['sequence_length_template']]
        if min_len:
            df = df[(df['sequence_length_template'] >= min_len)]
        else:
            min_len = 0
        if max_len:
            df = df[(df['sequence_length_template'] <= max_len)]
        else:
            max_len = max(df['sequence_length_template'])
        if sample and len(df) > sample: 
            df = df.sample(sample)
        
        # Auto correct windows size if too long
        if max_len-min_len < win_size:
            win_size = max_len-min_len
        
        # Plot
        fig, ax = pl.subplots(figsize=figsize)
        # Plot the kde graph
        if kde:
            sns.kdeplot(df["sequence_length_template"], ax=ax, color=kde_color, alpha=kde_alpha, shade=not hist, gridsize=500,
                legend=False)
        # Plot a frequency histogram 
        if hist:
            ax = df['sequence_length_template'].plot.hist(
                bins=np.arange(min_len, max_len, win_size), ax=ax, normed=True, color=hist_color, alpha=hist_alpha, histtype='stepfilled')
        
        # Tweak the plot       
        t = ax.set_title ("Distribution of reads length")
        t = ax.set_xlabel("Length in bp")
        t = ax.set_ylabel("Read Frequency")
        
        if not min_freq:
            min_freq = 0
        if not max_freq:
            max_freq = ax.get_ylim()[1]
            
        t = ax.set_xlim([min_len, max_len])
        t = ax.set_ylim([min_freq, max_freq])
        
        return ax

    def output_over_time (self, level="reads", figsize=[30,7], color="orangered", alpha=0.5, win_size=0.25, cumulative=False, **kwargs):
        """
        Plot the output over the time of the experiment at read, base or event level
        * level
            Aggregate channel output results by "reads", "bases" or "events" [Default "reads"]
        * figsize
            Size of ploting area [Default [30,7]
        * color
            Color of the plot. Valid matplotlib color code [Default "orangered"]
        * alpha
            Opacity of the area from 0 to 1 [Default 0.5]
        * win_size
            Size of the bins in hours [Default 0.25]
        * cumulative
            cumulative histogram [Default False]
        => Return
            A matplotlib.axes object for further user customisation (http://matplotlib.org/api/axes_api.html)
        """
        
        df = self.df[["num_events", "sequence_length_template"]].copy()
        df["end_time"] = (self.df["start_time"]+self.df["duration"])/3600

        # Compute the mean, min and max for each win_size interval
        df2 = pd.DataFrame(columns=["reads", "bases", "events"])
        for t in np.arange(0, max(df["end_time"]), win_size):
            if cumulative:
                sdf = df[(df["end_time"] < t+win_size)]
            else:
                sdf = df[(df["end_time"] >= t) & (df["end_time"] < t+win_size)]
            df2.loc[t] =[len(sdf), sdf["sequence_length_template"].sum(), sdf["num_events"].sum()]

        # Plot the graph
        fig, ax = pl.subplots(figsize=figsize)
        df2[level].plot.area(ax=ax, color=color, alpha=alpha)

        # Tweak the plot
        t = ax.set_title ("Total {} over time".format(level))
        t = ax.set_xlabel("Experiment time (h)")
        t = ax.set_ylabel("{} count".format(level))
        t = ax.set_xlim (0, max(df2.index))
        t = ax.set_ylim (0, ax.get_ylim()[1])
        
        return ax
    
    def quality_over_time (self, figsize=[30,7], color="orangered", alpha=0.25, win_size=0.25, **kwargs):
        """
        Plot the evolution of the mean read quality over the time of the experiment at read, base or event level
        * figsize
            Size of ploting area [Default [30,7]
        * color
            Color of the plot. Valid matplotlib color code [Default "orangered"]
        * alpha
            Opacity of the area from 0 to 1 [Default 0.25]
        * win_size
            Size of the bins in hours [Default 0.25]
        => Return
            A matplotlib.axes object for further user customisation (http://matplotlib.org/api/axes_api.html)
        """
        
        # Slice the main dataframe
        df = self.df[["mean_qscore_template"]].copy()
        df["end_time"] = (self.df["start_time"]+self.df["duration"])/3600
        
        # Compute the mean, min and max for each win_size interval
        df2 = pd.DataFrame(columns=["mean", "min", "max", "q1", "q3"])
        for t in np.arange(0, max(df["end_time"]), win_size):
            sdf = df["mean_qscore_template"][(df["end_time"] >= t) & (df["end_time"] < t+win_size)]
            df2.loc[t] =[sdf.median(), sdf.min(), sdf.max(), sdf.quantile(0.25), sdf.quantile(0.75)]

        # Plot the graph
        fig, ax = pl.subplots(figsize=figsize)
        ax.fill_between(df2.index, df2["min"], df2["max"], color=color, alpha=alpha)
        ax.fill_between(df2.index, df2["q1"], df2["q3"], color=color, alpha=alpha)
        ax.plot(df2["mean"], color=color)
        
        # Tweak the plot
        t = ax.set_title ("Mean read quality over time (Median, Q1-Q3, Min-Max)")
        t = ax.set_xlabel("Experiment time (h)")
        t = ax.set_ylabel("Mean read PHRED quality")
        t = ax.set_xlim (0, max(df2.index))
        t = ax.set_ylim (0, ax.get_ylim()[1])
        
        return ax
        
    def reads_len_quality (self, figsize=12, kde=True, scatter=True, margin_plot=True, kde_cmap="copper", scatter_color="orangered",
        margin_plot_color="orangered", kde_alpha=1, scatter_alpha=0.01, margin_plot_alpha=0.5, sample=100000, kde_levels=10, kde_shade=False,
        min_len=None, max_len=None, min_qual=None, max_qual=None, **kwargs):
        """
        Draw a bivariate plot of read length vs mean read quality with marginal univariate plots.
        * figsize
            Size of square ploting area [Default 12]
        * kde
            If True plot a bivariate kernel density estimate [Default True]
        * scatter
            If True plot a scatter plot  [Default true]
        * margin_plot
            If True plot marginal univariate distributions [Default True]
        * kde_cmap / scatter_color / margin_plot_color
            Color map or color codes to use for the 3 plots [Default "copper", "orangered", "orangered"]
        * kde_alpha / scatter_alpha / margin_plot_alpha
            Opacity of the area from 0 to 1 for the 3 plots [Default 1, 0.01, 0.5]
        * sample
            If given, a n number of reads will be randomly selected instead of the entire dataframe [Default 100000]
        * kde_levels
            Number of levels for the central density plot [Default 10]
        * kde_shade
            If True the density curves will be filled [Default False]
        * min_len, max_len
            Minimal and maximal read length cut-offs for the plot [Default None]
        * min_qual, max_qual
            Minimal and maximal read quality cut-offs for the plot [Default None]
        => Return
            A seaborn JointGrid object with the plot on it. (http://seaborn.pydata.org/generated/seaborn.JointGrid.html)
        """
        
        # Select reads
        df = self.df[["sequence_length_template", "mean_qscore_template"]]
        if min_len:
            df = df[(df['sequence_length_template'] >= min_len)]
        if max_len:
            df = df[(df['sequence_length_template'] <= max_len)]
        if min_qual:
            df = df[(df['mean_qscore_template'] >= min_qual)]
        if max_qual:
            df = df[(df['mean_qscore_template'] <= max_qual)]
        if sample and len(df) > sample: 
            df = df.sample(sample)
            
        # Plot the graph
        g = sns.JointGrid("sequence_length_template", "mean_qscore_template", data=df, space=0.1, size=figsize)
            
        if kde:
            if kde_shade:
                g = g.plot_joint(sns.kdeplot, cmap=kde_cmap, alpha=kde_alpha, shade=True, shade_lowest=False, n_levels=kde_levels,)
            else:
                g = g.plot_joint(sns.kdeplot, cmap=kde_cmap, alpha=kde_alpha, shade=False, shade_lowest=False, n_levels=kde_levels, linewidths=1)
        if scatter:
            g = g.plot_joint(pl.scatter, color=scatter_color, alpha=scatter_alpha)
        if margin_plot:
            g = g.plot_marginals(sns.kdeplot, shade=True, color=margin_plot_color, alpha=margin_plot_alpha)
        
        # Tweak the plot
        t = g.ax_marg_x.set_title ("Mean read quality per sequence length")
        t = g.ax_joint.set_xlabel("Sequence length (bp)")
        t = g.ax_joint.set_ylabel("Mean read quality (PHRED)")

        return g
