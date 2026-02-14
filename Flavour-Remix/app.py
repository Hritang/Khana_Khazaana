import streamlit as st

st.title("Flavor Remix")
st.write("AI Ingredient Substitution Engine")

recipe = st.text_input("Enter Recipe Name")
ingredient = st.text_input("Ingredient to Replace")

if st.button("Run Prototype"):
    st.success("Prototype running successfully.")
    st.write("Next step: API integration.")
