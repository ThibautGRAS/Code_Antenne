# -*- coding: utf-8 -*-
"""
Main de calibration MEMS / microphones de référence
"""

from data.config_calib import Config
from src import read_info, visu, calibration


if __name__ == "__main__":

    visu.print_section("Calibration MEMS / microphones de référence")

    config = Config()

    FULL_CORRESPONDANCE_TABLE =  {
        1:  {3: 121, 4: 169, 5: 25, 6: 73},
        2:  {3: 122, 4: 170, 5: 26, 6: 74},
        3:  {3: 123, 4: 171, 5: 27, 6: 75},
        4:  {3: 124, 4: 172, 5: 28, 6: 76},
        5:  {3: 125, 4: 173, 5: 29, 6: 77},
        6:  {3: 126, 4: 174, 5: 30, 6: 78},         
        8:  {3: 128, 4: 176, 5: 32, 6: 80}
    }

    correspondance_table = FULL_CORRESPONDANCE_TABLE

    run_calibration = True
    run_post_from_csv = True

    if run_calibration:
        calibration.run_calibration(
            config=config,
            correspondance_table=correspondance_table,
            read_info=read_info,
            visu=visu,
            window_type="hann",
            plot_results=True
        )

    if run_post_from_csv:
        calibration.run_post_from_csv(
            out_folder=config.out_folder,
            base_name=config.base_name,
            unit="dB"
        )
