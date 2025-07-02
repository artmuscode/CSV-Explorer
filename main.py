from flask import Flask, render_template

app = Flask(__name__)

# Define static files directory
app.static_folder = 'static'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')


@app.errorhandler(404)
def not_found(error):
    return '404 Not Found', 404



if __name__ == '__main__':
    app.run(debug=True)