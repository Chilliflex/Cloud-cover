# Papers not downloaded automatically

These are behind Elsevier / ResearchGate / bot checks. Download them from a browser or institutional login and drop them into the matching folder.

## 3_irradiance_energy
- Hammer, Heinemann, Lorenz, Lückehe (1999). Short-term forecasting of solar radiation: a statistical approach using satellite data. Solar Energy 67, 139–150. https://doi.org/10.1016/S0038-092X(00)00038-4 (paywalled)
- Yang, Wang, Gueymard et al. (2022). A review of solar forecasting, its dependence on atmospheric sciences and implications for grid integration: Towards carbon neutrality. RSER 161, 112348. https://doi.org/10.1016/j.rser.2022.112348 (paywalled)
- Yang, Alessandrini et al. (2020). Verification of deterministic solar forecasts. Solar Energy 210, 20–37. https://doi.org/10.1016/j.solener.2020.04.019 (free to read on ScienceDirect, but scripted download is blocked)

## 4_india_insat (search hits worth having, no open PDF)
- Kamath & Srinivasan (2020). Validation of global irradiance derived from INSAT-3D over India. Solar Energy 202, 45–54. https://doi.org/10.1016/j.solener.2020.03.084 (the main INSAT-3D insolation validation paper)
- Parihar et al. (2024). Validation of cloud mask product from multi-channel satellite INSAT-3DR. Advances in Space Research. https://www.sciencedirect.com/science/article/abs/pii/S0273117724004241
- Mapping of Solar Resource based on INSAT 3D/3DR Surface Insolation product (2020 preprint). https://www.preprints.org/manuscript/202006.0328/v1
- Masoom & Bansal (2021). Solar irradiance forecasting using NWP model and INSAT-3D based satellite model. EU PVSEC. https://www.researchgate.net/publication/384427403
- Enhancing BoB cyclone precipitation nowcasting with deep learning: ConvLSTM using INSAT-3D data. J. Hydrology (2025). https://www.sciencedirect.com/science/article/abs/pii/S0022169425012491
- MeghNA: Cloud detection and motion prediction in INSAT images. https://www.researchgate.net/publication/356830965 (code: https://github.com/shlokashah/MeghNA)

## Notes
- The CloudCast (Partio 2025) PDF is the arXiv v2 (May 2025), matching the accepted AIES version. The AMS site blocked a direct download.
- The fmidev/cloudcast repo is cloned to ../cloudcast_fmidev
- MOSDAC has no separate insolation ATBD. Both algorithms are in INSAT3D_ATBD_May2015_geophysical_products.pdf: Ch. 2 Cloud Mask (p. 14) and Ch. 20 Surface Insolation over Land (p. 335). HDF5 field layout and L1B calibration tables are in INSAT3D_Data_Products_Format_Document_HDF5.pdf (Chapter 2 and Appendix I).
