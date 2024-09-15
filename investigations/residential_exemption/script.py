
import asyncio
import pandas as pd

from playwright.async_api import async_playwright
from data.connect_db import get_db

from tqdm import tqdm

con = get_db()
query = """
    select
        id,
        \"PROP_ID\",
        \"USE_CODE\"
    from 
        \"M308Assess_CY22_FY23\"
    where
        -- we only care about MFH uses since that's where the fraud is most likely
        \"USE_CODE\" like any(array['102', '103', '104'])
"""

assess_df = pd.read_sql(query, con)

prop_ids = assess_df["PROP_ID"]

URL = "https://web-server.city.waltham.ma.us/governecomponents/webuserinterface"

P_ID_INPUT_SUFFIX = "WebPortal/WEB_PT_MAIN.aspx?command=REPORTPARAMETERSTYLE&style=&group=PidGroup"

REPORT_URL_SUFFIX = "Report/Web_Report_CrystalViewer.aspx?REPORTNAME=E:\Govern\eGov\Reports_TX_Site\WAL_WEB_TX.rpt&ReportParameter=YEAR_ID=2,024.00;CURRENT_YEAR_ID=2025"

async def main():

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        for prop_id in tqdm(prop_ids):
            page = await browser.new_page()
            await page.goto(URL)
            
            # page url updates, ex:
            # 'https://web-server.city.waltham.ma.us/GovernEcomponents/WebUserInterface/(S(udtoc051aj4n5nwej0y2agel))/WebPortal/WEB_PT_MAIN.aspx?command=REPORTPARAMETERSTYLE&style=&group=PidGroup'
            
            # slice everything from WebPortal on and update the URL above, used
            # for the rest of the session
            SESSION_URL = page.url[:page.url.find("WebPortal")]
            
            # need to input a parcel id first because waltham uses some other system without an apparent pattern        
            await page.goto(SESSION_URL + P_ID_INPUT_SUFFIX)
            
            # select option to search by parcel ID
            await page.locator("#objWP_reportparameterstyle_ESearchManager1_rdblStyles_1").click()
            
            # submit... maybe navigates? url doesn't change
            await page.locator("#objWP_reportparameterstyle_ESearchManager1_cmdLoadStyleContent").click()
            
            # input parcel id
            prop_id_parts = prop_id.split()
            
            await page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_0").fill(prop_id_parts[0])
            await page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_1").fill(prop_id_parts[1])
            await page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_2").fill(prop_id_parts[2])

            if len(prop_id_parts) == 4:
                # for multifamily homes and such on the same parcel
                await page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_msk_GFD0_3").fill(prop_id_parts[3])

            async with page.expect_navigation():
                await page.locator("#objWP_reportparameterstyle_ESearchManager1_Web_CO_SearchPanel1_btnGo").click()

            # should load a table with one item
            waltham_parcel_id = await page.locator("tr.GRID-ITEM").locator(":nth-child(4)").inner_text()
            
            # waltham parcel id is a parameter
            await page.goto(SESSION_URL + REPORT_URL_SUFFIX + f";P_ID={waltham_parcel_id}")

            async with page.expect_event("download") as event_info:
                await page.locator("#Web_Report_CrystalViewer1_MyReportManager_imgPrint2").click()

            download = await event_info.value
            await download.save_as(f"./investigations/residential_exemption/reports/{prop_id}_{waltham_parcel_id}.pdf")

        await browser.close()
        
asyncio.run(main())


