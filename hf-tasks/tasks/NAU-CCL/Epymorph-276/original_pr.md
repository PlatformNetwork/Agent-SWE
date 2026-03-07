# NAU-CCL/Epymorph-276 (original PR)

NAU-CCL/Epymorph (#276): A new ADRIO for daily influenza data at the state level. 

This ADRIO is designed to draw from two columns in the dataset COVID-19 Reported Patient Impact and Hospital Capacity by State Timeseries (RAW) at https://healthdata.gov/Hospital/COVID-19-Reported-Patient-Impact-and-Hospital-Capa/g62h-syeh/about_data

The dataset does not appear to have any missing values, but I retained the missing value checks just in case. Example setup of the ADRIO would look like

`cdcadrio_H = cdc.InfluenzaStateHospitalizationDaily(
    fix_missing=0,
    column = 'hospitalizations'
).with_context(
    time_frame=TimeFrame.of("2022-09-15", 7 * 26 + 1),
    scope=StateScope.in_states(["AZ","NV"], year=2019),
)`

where column can be the string hospitalizations or admissions. 
