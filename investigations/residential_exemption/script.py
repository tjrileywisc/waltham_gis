import asyncio
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright


URL = "https://web-server.city.waltham.ma.us/governecomponents/webuserinterface"

URL_SUFFIX = "Report/Web_Report_CrystalViewer.aspx?REPORTNAME=E:\Govern\eGov\Reports_TX_Site\WAL_WEB_TX.rpt&ReportParameter=YEAR_ID=2,024.00;P_ID=25039;CURRENT_YEAR_ID=2025"


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL)
    
    # page url updates, ex:
    # 'https://web-server.city.waltham.ma.us/GovernEcomponents/WebUserInterface/(S(udtoc051aj4n5nwej0y2agel))/WebPortal/WEB_PT_MAIN.aspx?command=REPORTPARAMETERSTYLE&style=&group=PidGroup'
    
    # slice everything from WebPortal on and update the URL abovee
    URL = page.url[:page.url.find("WebPortal")] + URL_SUFFIX
    
    page.goto(URL)
    
    with page.expect_event("download") as event_info:
        page.locator("#Web_Report_CrystalViewer1_MyReportManager_imgPrint2").click()

    download = event_info.value
    download.save_as("./investigations/residential_exemption/reports/25039.pdf")
    
    # the actual report is in an iframe
    # document_iframe = page.frame_locator("#document")
    # exemption = document_iframe.locator("#BASEEXEMPTVALUE1").locator("span")
    # #print(exemption.all_text_contents())
    # document_iframe.owner.screenshot(path=f'example.png')
    browser.close()


