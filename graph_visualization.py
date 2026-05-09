import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# Sample data based on the screenshot analysis
# You can replace this with your actual data
data = {
    'Benchmark': [
        'MMLU', 'GSM8K', 'AIME', 'HumanEval', 'MBPP', 
        'SWE-bench', 'Multi-Int', 'Cot-Reasoning', 'Web-Search', 'Tool-Use'
    ],
    'Category': [
        'Reasoning Capabilities', 'Reasoning Capabilities', 'Reasoning Capabilities',
        'Reasoning Capabilities', 'Reasoning Capabilities',
        'Agentic Capabilities', 'Agentic Capabilities', 'Agentic Capabilities',
        'Agentic Capabilities', 'Agentic Capabilities'
    ],
    'DeepSeek-V3.2-Speciale': [85.2, 92.1, 67.3, 78.4, 81.2, 45.6, 52.3, 61.8, 58.9, 63.4],
    'DeepSeek-V3.2-Thinking': [88.7, 94.5, 73.2, 82.1, 85.6, 51.2, 58.7, 68.4, 64.2, 69.8],
    'GPT-5-High': [91.3, 96.2, 78.9, 85.7, 89.3, 58.4, 65.2, 74.1, 71.6, 76.2],
    'Claude-4.5-Sonnet': [89.8, 95.1, 75.6, 83.4, 87.1, 54.7, 61.8, 70.5, 67.3, 72.1],
    'Gemini-3.0-Pro': [93.2, 97.8, 81.4, 88.9, 91.7, 62.3, 71.5, 78.9, 75.8, 81.4]
}

# Create DataFrame
df = pd.DataFrame(data)

# Define colors for each model
colors = {
    'DeepSeek-V3.2-Speciale': '#87CEEB',      # Light blue
    'DeepSeek-V3.2-Thinking': '#4169E1',      # Royal blue with pattern
    'GPT-5-High': '#D3D3D3',                  # Light gray
    'Claude-4.5-Sonnet': '#A9A9A9',           # Medium gray
    'Gemini-3.0-Pro': '#696969'               # Dark gray
}

# Create figure with dual y-axis
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Add bars for each model
models = ['DeepSeek-V3.2-Speciale', 'DeepSeek-V3.2-Thinking', 'GPT-5-High', 
          'Claude-4.5-Sonnet', 'Gemini-3.0-Pro']

for model in models:
    fig.add_trace(
        go.Bar(
            name=model,
            x=df['Benchmark'],
            y=df[model],
            marker_color=colors[model],
            marker_line_width=1,
            marker_line_color='black',
            opacity=0.85,
            customdata=df[model],
            hovertemplate=f'<b>{model}</b><br>Benchmark: %{{x}}<br>Accuracy: %{{customdata:.1f}}%<extra></extra>',
            legendgroup=model,
            showlegend=True
        ),
        secondary_y=False
    )

# Add Codeforces Rating bars (right y-axis)
# Using a subset of benchmarks with ratings
rating_data = {
    'DeepSeek-V3.2-Speciale': [2100, 2200, 1800, 1950, 2050, 1600, 1750, 1850, 1700, 1800],
    'DeepSeek-V3.2-Thinking': [2250, 2350, 1950, 2100, 2200, 1750, 1900, 2000, 1850, 1950],
    'GPT-5-High': [2400, 2500, 2100, 2250, 2350, 1900, 2050, 2150, 2000, 2100],
    'Claude-4.5-Sonnet': [2350, 2450, 2050, 2200, 2300, 1850, 2000, 2100, 1950, 2050],
    'Gemini-3.0-Pro': [2500, 2600, 2200, 2350, 2450, 2000, 2150, 2250, 2100, 2200]
}

for model in models:
    fig.add_trace(
        go.Bar(
            name=f'{model} (Rating)',
            x=df['Benchmark'],
            y=rating_data[model],
            marker_color=colors[model],
            marker_line_width=1,
            marker_line_color='black',
            opacity=0.6,
            customdata=rating_data[model],
            hovertemplate=f'<b>{model}</b><br>Benchmark: %{{x}}<br>Codeforces Rating: %{{customdata:.0f}}<extra></extra>',
            legendgroup=f'{model} (Rating)',
            showlegend=False
        ),
        secondary_y=True
    )

# Update layout
fig.update_layout(
    title={
        'text': 'AI Model Performance Comparison',
        'y': 0.95,
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {'size': 20, 'family': 'Arial'}
    },
    barmode='group',
    bargap=0.15,
    bargroupgap=0.1,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=11)
    ),
    hovermode='x unified',
    plot_bgcolor='white',
    paper_bgcolor='white',
    margin=dict(l=100, r=50, t=80, b=120),
    height=700,
    width=1400
)

# Update axes
fig.update_xaxes(
    title_text='Benchmarks',
    title_font=dict(size=14),
    tickangle=45,
    tickfont=dict(size=10),
    gridcolor='lightgray'
)

fig.update_yaxes(
    title_text='Accuracy / Pass@1 (%)',
    title_font=dict(size=14),
    range=[0, 105],
    tickformat='.1f',
    gridcolor='lightgray',
    secondary_y=False
)

fig.update_yaxes(
    title_text='Codeforces Rating',
    title_font=dict(size=14),
    range=[0, 3000],
    tickformat='.0f',
    gridcolor='lightgray',
    secondary_y=True
)

# Add category annotations
for i, category in enumerate(['Reasoning Capabilities', 'Agentic Capabilities']):
    fig.add_annotation(
        text=category,
        x=(df['Benchmark'].index[df['Category'] == category].min() + 
           df['Benchmark'].index[df['Category'] == category].max()) / 2,
        y=max(df['DeepSeek-V3.2-Speciale']) + 5,
        showarrow=False,
        font=dict(size=12, color='darkblue', family='Arial'),
        align="center",
        bordercolor='darkblue',
        borderwidth=1,
        borderpad=4,
        bgcolor='lightblue',
        opacity=0.7,
        xref='x',
        yref='y'
    )

# Add value labels on top of bars (for main accuracy bars)
for model in models:
    for i, value in enumerate(df[model]):
        fig.add_annotation(
            x=df['Benchmark'].iloc[i],
            y=value + 2,
            text=f'{value:.1f}',
            showarrow=False,
            xanchor='center',
            yanchor='bottom',
            font=dict(size=8, color='black'),
            bgcolor='white',
            bordercolor='black',
            borderwidth=0.5
        )

# Make it interactive
fig.update_traces(
    hoverinfo='text',
    hoverlabel=dict(
        bgcolor='white',
        font_size=12,
        font_family='Arial'
    )
)

# Add legend for categories
fig.add_trace(go.Scatter(
    x=[df['Benchmark'][0]],
    y=[0],
    mode='markers',
    marker=dict(color='lightblue', size=10),
    name='Reasoning Capabilities',
    showlegend=True
))

fig.add_trace(go.Scatter(
    x=[df['Benchmark'][5]],
    y=[0],
    mode='markers',
    marker=dict(color='lightgreen', size=10),
    name='Agentic Capabilities',
    showlegend=True
))

# Show the graph
fig.show()

# Save to HTML
fig.write_html('dynamic_graph.html')
print("Graph saved as 'dynamic_graph.html'")

# Optional: Create a simpler version with just the main data
def create_simple_version():
    fig_simple = go.Figure()
    
    for model in models:
        fig_simple.add_trace(
            go.Bar(
                name=model,
                x=df['Benchmark'],
                y=df[model],
                marker_color=colors[model],
                opacity=0.85,
                customdata=df[model],
                hovertemplate=f'<b>{model}</b><br>Benchmark: %{{x}}<br>Accuracy: %{{customdata:.1f}}%<extra></extra>'
            )
        )
    
    fig_simple.update_layout(
        title='AI Model Performance - Accuracy/Pass@1 (%)',
        barmode='group',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=1, xanchor="right"),
        xaxis_title='Benchmarks',
        yaxis_title='Accuracy / Pass@1 (%)',
        height=600,
        width=1200
    )
    
    fig_simple.show()
    fig_simple.write_html('simple_graph.html')
    print("Simple graph saved as 'simple_graph.html'")

# Uncomment to create simple version
# create_simple_version()
