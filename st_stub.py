"""Import this BEFORE `import app` to stub Streamlit so app.py does not launch
its UI. Lets the benchmark reuse the live pipeline functions."""
import sys, types

class _Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, k): return lambda *a, **kw: False

class _SS(dict):
    def __getattr__(self, k): return self.get(k)
    def __setattr__(self, k, v): self[k] = v

def _install():
    st = types.ModuleType("streamlit")
    noop = lambda *a, **k: None
    cm = lambda *a, **k: _Ctx()
    for n in ("set_page_config","markdown","error","write","caption","divider",
              "rerun","stop","title","subheader","header","info","warning","success"):
        setattr(st, n, noop)
    st.session_state = _SS(messages=[], pending=None)
    st.columns = lambda n, *a, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
    st.button = lambda *a, **k: False
    st.chat_input = lambda *a, **k: None
    st.chat_message = cm; st.spinner = cm; st.expander = cm; st.container = cm
    st.cache_resource = lambda f=None, **k: (f if callable(f) else (lambda g: g))
    st.cache_data = st.cache_resource
    sys.modules["streamlit"] = st

_install()
