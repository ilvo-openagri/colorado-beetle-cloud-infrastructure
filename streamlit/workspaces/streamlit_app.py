import streamlit as st
from st_pages import add_page_title, get_nav_from_toml, hide_pages
from PIL import Image
from dotenv import load_dotenv


# Load dotenv:
load_dotenv(".env")

st.set_page_config(
    page_title="OpenAgri SIP3 - Dashboard",
    page_icon=Image.open("icons/openagri.png"),
    layout="wide",
)


nav = get_nav_from_toml(".streamlit/pages.toml")
# hide_pages(["Detailed statistics"])
st.logo("icons/openagri.png", size="large")
pg = st.navigation(nav)
add_page_title(pg)
pg.run()
