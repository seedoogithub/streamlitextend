const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');

const glob = require('glob');

module.exports = {
  mode: 'development', // Use development mode for more readable code
  devtool: 'source-map',
  entry: {
    ...glob.sync('./src/*.js').reduce((acc, path) => {
        const entry = path.replace('/src/', '/').replace('.js', '');;
        acc[entry] = path;
      return acc;
    }, {}),
    WebsocketButton: './src/websocket_button/index.tsx',
    ModalComponent: './src/modal/index.tsx'
  },
  output: {
    publicPath: '',
    filename: '[name]/bundle.js',
    path: path.resolve(__dirname, 'build'),
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js', '.jsx'],
  },
  module: {
    rules: [
      {
        test: /\.(jsx)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-react']
          }
        }
      },
     {
        test: /\.css$/,
        use: [
          'style-loader',
          'css-loader'
        ]
      },
      {
        test: /\.(ts|tsx)$/,
        exclude: /node_modules/,
        use: 'ts-loader',
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: path.resolve(__dirname, 'src/websocket_button/template.html'), // Path to your template file
      filename: 'WebsocketButton/index.html', // Output file
      chunks: ['WebsocketButton'],
      inject: false,
      publicPath: '' // This is the important line
    }),
    new HtmlWebpackPlugin({
      template: path.resolve(__dirname, 'src/modal/template.html'), // Path to your template file
      filename: 'ModalComponent/index.html', // Output file
      chunks: ['ModalComponent'],
      inject: false,
      publicPath: '' // This is the important line

    }),

    new CopyPlugin({
      patterns: [
        { from: 'public', to: '' }, // copies all files from `public` to `build/public`
      ],
    }),
  ],
};
