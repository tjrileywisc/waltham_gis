
import pandas as pd

from playwright.sync_api import sync_playwright
from data.connect_db import get_db

from tqdm import tqdm

con = get_db()
query = "select \"PROP_ID\" from \"M308Assess_CY22_FY23\" limit 10"

assess_df = pd.read_sql(query, con)

prop_ids = assess_df["PROP_ID"]

URL = "https://web-server.city.waltham.ma.us/governecomponents/webuserinterface"

P_ID_INPUT_SUFFIX = "WebPortal/WEB_PT_MAIN.aspx?command=REPORTPARAMETERSTYLE&style=&group=PidGroup"

REPORT_URL_SUFFIX = "Report/Web_Report_CrystalViewer.aspx?REPORTNAME=E:\Govern\eGov\Reports_TX_Site\WAL_WEB_TX.rpt&ReportParameter=YEAR_ID=2,024.00;CURRENT_YEAR_ID=2025"


with sync_playwright() as p:
    browser = p.chromium.launch()
    
    for prop_id in tqdm(prop_ids):
        page = browser.new_page()
        page.goto(URL)
        
        # page url updates, ex:
        # 'https://web-server.city.waltham.ma.us/GovernEcomponents/WebUserInterface/(S(udtoc051aj4n5nwej0y2agel))/WebPortal/WEB_PT_MAIN.aspx?command=REPORTPARAMETERSTYLE&style=&group=PidGroup'
        
        # slice everything from WebPortal on and update the URL above, used
        # for the rest of the session
        SESSION_URL = page.url[:page.url.find("WebPortal")]
        
        # need to input a parcel id first because waltham uses some other system without an apparent pattern        
        page.goto(SESSION_URL + P_ID_INPUT_SUFFIX)
        
        # select option to search by parcel ID
        page.locator("#objWP_reportparameterstyle_ESearchManager1_rdblStyles_1").click()
        
        # submit... maybe navigates? url doesn't change
        page.locator("#objWP_reportparameterstyle_ESearchManager1_cmdLoadStyleContent").click()
        
        # input parcel id
        prop_id_parts = prop_id.split()
        
        page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_0").fill(prop_id_parts[0])
        page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_1").fill(prop_id_parts[1])
        page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_2").fill(prop_id_parts[2])

        if len(prop_id_parts) == 4:
            # for multifamily homes and such on the same parcel
            page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_3").fill(prop_id_parts[3])

        with page.expect_navigation():
            page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_btnGo").click()

        # should load a table with one item
        waltham_parcel_id = page.locator("tr.GRID-ITEM").locator(":nth-child(4)").inner_text()
        
        # waltham parcel id is a parameter
        page.goto(SESSION_URL + REPORT_URL_SUFFIX + f";P_ID={waltham_parcel_id}")

        with page.expect_event("download") as event_info:
            page.locator("#Web_Report_CrystalViewer1_MyReportManager_imgPrint2").click()

        download = event_info.value
        download.save_as(f"./investigations/residential_exemption/reports/{prop_id}_{waltham_parcel_id}.pdf")

    browser.close()


