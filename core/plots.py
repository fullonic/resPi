from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go

from core.utils import string_to_float


class Plot:
    """Generate all necessary kind of application plots."""

    def __init__(
        self,
        data,
        x_axis,
        y_axis,
        title,
        *,
        dst=None,
        fname="dataframe",
        output="html",
    ):  # noqa
        self.data = data
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.title = title
        self.output = output
        self.fname = fname
        self.dst = dst

    def create(self):
        """Create a plot for each close loop data."""
        x = self.data[self.x_axis]
        y = self.data[self.y_axis]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                name=self.y_axis,
                line=dict(color="blue", width=1),
                showlegend=True,
            )
        )

        fig1 = px.scatter(self.data, x=x, y=y, trendline="ols")
        fig1.update_traces(line=dict(color="#861d4f", width=3))
        fig.update_xaxes(title_text=f"<b>{self.x_axis}</b>")
        fig.update_yaxes(title_text=f"<b>{self.y_axis}</b>")
        trendline = fig1.data[1]
        fig.add_trace(trendline)
        formula, rsqt = trendline.hovertemplate.split("<br>")[1:3]
        title = f"""<b>{self.title}</b><br>{formula}<br>{rsqt}"""
        fig.update_layout(dict(title=title, showlegend=True))

        config = {"editable": True, "displaylogo": False}

        fig.write_html(f"{self.dst}/{self.fname}.{self.output}", config=config)
        return fig1

    def create_global_plot(self, fname=None, markers=[]):
        """Plot all information from document before any kind of data manipulation."""
        from plotly.subplots import make_subplots

        if fname not in ["C1", "C2"]:
            x = self.data[self.x_axis][::30]
            y = self.data[self.y_axis][::30]
        else:
            x = self.data[self.x_axis]
            y = self.data[self.y_axis]

        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                name=self.title,
                line=dict(color="blue", width=1),
                showlegend=True,
            ),
            secondary_y=False,
        )
        temp = [
            string_to_float(t)
            for t in list(self.data["SDWA0003000061      , CH 1 temp [°C]"])
        ]

        fig.add_trace(
            go.Scatter(
                x=x,
                y=temp,
                name="Temperatura",
                line=dict(color="red", width=1),
                showlegend=True,
            ),
            secondary_y=True,
        )
        # MARKERS
        # nloops = markers[:-1]
        nloops = [m - markers[0] for m in markers]
        y = [9.5] * len(markers)
        size = [2] * len(markers)
        loop = [
            f'<a id="marker_" name="{i + 1}">{i + 1}</a>' for i, _ in enumerate(markers)
        ]

        points = px.scatter(x=nloops, y=y, size=size, text=loop,)
        fig.add_trace(points.data[0])

        # Set x-axis title
        fig.update_xaxes(title_text=f"<b>{self.x_axis}</b>")
        fig.update_yaxes(title_text=f"<b>{self.y_axis}</b>", secondary_y=False)
        fig.update_yaxes(title_text="<b>Temperatura</b>", secondary_y=True)
        fig.update_layout(title=f"<b>{fname.title()} Gràfic global</b>")
        template_folder = Path().resolve() / "templates/previews"
        fig.write_html(f"{template_folder}/{fname}.html")
