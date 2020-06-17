""" Utilities to work with the ETA result data
"""
import logging
import time
import numpy as np

import etabackend.tk.utils


def save_data(xdata, ydata, data_file, result_path, label, header=None):
    """ Stores the data in a local result folder.
    """
    data_file = Path(data_file)
    result_path = Path(result_path)
    result_path.mkdir(parents=True, exist_ok=True)  # Create analyzed folder
    
    # create unique index for file
    file_index = 0
    while (result_path / f"{data_file.stem}_{label}_{file_index:0=3d}.txt").exists():
        file_index += 1
    
    np.savetxt(result_path / f"{data_file.stem}_{label}_{file_index:0=3d}.txt",
                np.transpose([xdata, ydata]), delimiter='\t', 
                header=header)

class ETAResult:
    """ Analyses a file using the eta library 
        for correlation data.
    """
    def __init__(self, file, bins, bin_factor, group,
                 records_per_cut=None, kernel=None, 
                 interval=0.1, timeout=0.2, simulate_growth=False):
        """ Calculates the result for the file regularly
            file: str or Path of file currently investigated
            bin_factor: The multiplication factor for each bin.
            interval: The time to wait in seconds
            timeout: How long to wait for enough data until frame is skipped (seconds)
            simulate_growth: Behave as if we have a growing file.
        """
        self.logger = logging.getLogger('etabackend.frontend')

        self.file = file
        self.group = group
        self.bins = bins
        self.bin_factor = bin_factor
        self.records_per_cut = records_per_cut
        self.interval = interval
        self.timeout = timeout

        self.eta = kernel
        self._simulate_growth = simulate_growth
        self.set_accumulation_mode()
        self._inspect_file()
        self.context = None

    def run(self):
        return self._run_eta_evaluation()
    
    def update(self):
        return self._update_eta_evaluation()

    def _inspect_file(self):
        # First cut to detect file properties and rate estimation
        self.cut = self.eta.clip_file(
            self.file, modify_clip=None, read_events=1, format=-1, wait_timeout=0)

        if self.records_per_cut is None:
            self._estimate_growth()

        if self._simulate_growth is False:
            file_size = self.file.stat().st_size
            file_size = file_size - self.cut.fseekpoint
            self.existing_records = file_size//self.cut.BytesofRecords
        else:
            self.existing_records = self.records_per_cut
            self.logger.info("Simulate Growth is activated.")

    def _estimate_growth(self):
        """ Estimates the grow rate per second, will sleep for 1000ms.
        The event loop continues running.
        """
        self.logger.info('Estimating File growth.')
        file_size_old = self.file.stat().st_size
        time.sleep(1)
        file_size_new = self.file.stat().st_size
        self.logger.info('Done.')
        
        self.growth_rate = (file_size_new - file_size_old) / \
            self.cut.BytesofRecords  # Bytes per record
        self.records_per_cut = int(self.growth_rate * self.interval)

    def set_accumulation_mode(self):
        self.mode = 'accumulation'

    def set_alignment_mode(self):
        self.mode = 'align'

    def toggle_mode(self, event):
        if self.mode == 'align':
            self.set_accumulation_mode()
        elif self.mode == 'accumulation':
            self.set_alignment_mode()

    def _run_eta_evaluation(self):
        """ Calculates all available data.
            Calls calculate_result that needs to be implemented by the result class.
        """
        self.cut = self.eta.clip_file(self.file, modify_clip=None,
                                      read_events=self.existing_records, wait_timeout=0.5)  # Start always from begining of file

        result, self.context = self.eta.run({"timetagger1": self.cut}, resume_task=None, group=self.group,
                                            return_task=True,
                                            return_results=True, max_autofeed=1)
        
        self.xdata, self.ydata = self.calculate_result(result)
        self.lastupdate = time.time()
        self.max_value = np.amax(self.ydata)
        self.y_max = self.max_value*1.5

    def _update_eta_evaluation(self):
        """ Calculates the next step of data.
            Calls calculate_result that needs to be implemented by the result class.
        """
        check_ret = self.eta.clip_file(self.file, modify_clip=self.cut,
                                       read_events=self.records_per_cut, wait_timeout=self.timeout)
        if not check_ret:
            # No new data available
            return
        
        self.logger.info('New data available for a calculating a new block.')

        self.cut = check_ret  # save the ret to cut
        context = self.context if self.mode == 'accumulation' else None
        result, self.context = self.eta.run({"timetagger1": self.cut}, resume_task=context, group=self.group,
                                            return_task=True,
                                            return_results=True, max_autofeed=1)

        
        self.xdata, self.ydata = self.calculate_result(result)
        self.max_value = np.amax(self.ydata)
        self.y_max = self.max_value*1.5
        
        self.lastupdate = time.time()

    def calculate_result(self, result):
        """ Gets the ETA result dict and returns x and y data as array.
        """
        self.logger.error('calculate_result needs to be implemented by a child class of ETAResult')
        raise NotImplementedError()

        # Example DEAD code
        hist1 = result['h3']
        hist2 = result['h4']
        hist0 = result["h4_zero"]
        hist1[0] += hist0[0]
        xdata = np.arange(-self.hist2.size, self.hist1.size)*self.bin_factor
        ydata = np.concatenate((self.hist2[::-1],self.hist1))

        return xdata, ydata                        