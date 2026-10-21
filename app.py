from pathlib import Path
import runpy
import streamlit as st
if st.query_params.get('workspace')=='research':
    runpy.run_path(str(Path(__file__).with_name('research_app.py')),run_name='__main__')
else:
    from simple_ui import main
    main(public_demo=False)
