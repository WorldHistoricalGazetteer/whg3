const path = require('path');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = {
  mode: 'production',
  watch: true,
  watchOptions: {
    poll: 1000, // Check for changes every second
  },
  entry: {
    whg: '/app/whg/webpack/js/whg.js',
    maptiler_sdk: '/app/whg/webpack/js/maptiler-sdk.js',
    gis_resources: '/app/whg/webpack/js/gis_resources.js',
    search_functions: '/app/whg/webpack/js/search_resources.js',
    home: '/app/whg/webpack/js/home.js',
    search: '/app/whg/webpack/js/search.js',
    portal: '/app/whg/webpack/js/portal.js',
    places: '/app/whg/webpack/js/places.js',
    tasks: '/app/whg/webpack/js/tasks.js',
    areas: '/app/whg/webpack/js/areas.js',
    ds_browse: '/app/whg/webpack/js/ds_browse.js',
  },
  output: {
    filename: '[name].bundle.js',
    path: '/app/whg/static/webpack',
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, 'css-loader'],
      },
      {
        test: /\.scss$/,
        use: [MiniCssExtractPlugin.loader, 'css-loader', 'sass-loader'],
      },
    ],
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: '[name].bundle.css',
    }),
  ],
  resolve: {
    alias: {
      'jquery': path.resolve(__dirname, 'static/admin/js/vendor/jquery/jquery.js'),
    },
  },
  optimization: {
    minimize: false,
    minimizer: [
      new TerserPlugin({
        terserOptions: {
          format: {
            comments: false,
          },
        },
        extractComments: false,
      }), // Minimize JavaScript using TerserPlugin
      new CssMinimizerPlugin(), // Minimize CSS using CssMinimizerPlugin
    ],
  },
};
