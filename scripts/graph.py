import plotly.graph_objs as go
import plotly.express as px
import pandas as pd

table_ = "/home/somnium/Desktop/dataframe_2.xlsx"
df = pd.read_excel(table_)
df.tail()
y, x = df.columns[-2:]
x = df[x]
y = df[y]

fig = px.line(df, x=x, y=y, title="O2 Evolution")
# fig.add_scatter(x=df["Times"], y=df["Temperature"], mode='lines', name="test")
fig.write_html("test.html")
