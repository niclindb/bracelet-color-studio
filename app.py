from turtle import color

from flask import Flask, redirect, render_template as template, request
import requests
import re
from dmc_dict import dmc_dict as dmc_colors

app = Flask(__name__)

def remove_wm_tags(svg_content):
    # This removes any <text> tag that contains the 'wm' class
    clean_svg = re.sub(r'<text class="wm[01]".*?</text>', '', svg_content)
    return clean_svg

def get_svgs(design_number):
    try:
        url = f"https://www.braceletbook.com/patterns/normal/{design_number}/"
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        html_content = response.text
        pattern_url = re.search(r'https://.*?pattern\.svg', html_content).group(0)
        preview_url = pattern_url.replace('pattern.svg', 'preview.svg')
        response = requests.get(preview_url)
        response.raise_for_status()  # Check if the request was successful
        preview_svg = response.text

        response = requests.get(pattern_url)
        response.raise_for_status()  # Check if the request was successful
        pattern_svg = response.text
    except Exception as e:
        return None, None
    return remove_wm_tags(pattern_svg), remove_wm_tags(preview_svg)

@app.route('/')
def index():
    return template('index.html')

@app.route('/submit-design', methods=['POST'])
def submit_design():
    return redirect('/design/' + request.form.get('design_number'))


@app.route('/design/<int:design_number>')
def design(design_number):  
    pattern_svg, preview_svg = get_svgs(design_number)

    hex_codes = request.args.get('hex_codes', '').split(',') if request.args.get('hex_codes') else []
    hex_codes = ['#' + code for code in hex_codes]
    floss_codes = [dmc_colors.get(code.lower(), '') for code in hex_codes]
    if pattern_svg is None:
        return template('index.html', error="Could not retrieve SVG. Please check the design number and try again.")
    return template('design.html', pattern=pattern_svg, preview=preview_svg, hex_codes=hex_codes, floss_codes=floss_codes)

@app.route('/generate-colors/<int:num_colors>', methods=['GET', 'POST'])
def colors(num_colors=None):
    colors = set(dmc_colors)
    preview_svg = request.form.get('preview_svg', '')
    original_url = request.referrer.split('?')[0]  # Get the URL without query parameters
    design_number = original_url.split('/')[-1]
    return template('colors.html', num_colors=num_colors,design_number=design_number, preview_svg=preview_svg, colors=list(colors))


if __name__ == '__main__':
    app.run()
    