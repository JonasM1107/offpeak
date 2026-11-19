Copies of the Blender models in app/ui/models/ (made by scripts/blender/), for the 3D
site on the landing page: Streamlit serves only app/static/ to a page. Never edit these;
tests/test_landing.py checks that every copy is identical to its original.
