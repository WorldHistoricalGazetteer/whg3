// /webpack.config.js

const path = require('path');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const Dotenv = require('dotenv-webpack');
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;

module.exports = {
	mode: 'production',
	watch: true,
	watchOptions: {
		poll: 1000, // Check for changes every second
	},
	entry: {
		base: '/app/whg/webpack/js/base.js',
		whg: '/app/whg/webpack/js/whg.js',
		maptiler_sdk: '/app/whg/webpack/js/maptiler-sdk.js',
		whg_maplibre: '/app/whg/webpack/js/whg_maplibre.js',
		gis_resources: '/app/whg/webpack/js/gis_resources.js',
		search_functions: '/app/whg/webpack/js/search_resources.js',
		home: '/app/whg/webpack/js/home.js',
		search: '/app/whg/webpack/js/search.js',
		portal: '/app/whg/webpack/js/portal.js',
		places: '/app/whg/webpack/js/places.js',
		tasks: '/app/whg/webpack/js/tasks.js',
		areas: '/app/whg/webpack/js/areas.js',
		ds_browse: '/app/whg/webpack/js/ds_browse.js',
		review: '/app/whg/webpack/js/review.js',
		gallery: '/app/whg/webpack/js/gallery.js',
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
		new Dotenv({
			path: '/app/.env/.dev-whg3',
		}),
		new MiniCssExtractPlugin({
			filename: '[name].bundle.css',
		}),
		new BundleAnalyzerPlugin({
			analyzerMode: 'static', // `server` option is very slow
			reportFilename: 'webpackReport.html',
			generateStatsFile: true,
			statsFilename: 'stats.json',
		}),
	],
	resolve: {
		modules: [
			path.resolve(__dirname, 'static/admin/js/vendor'),
			path.resolve(__dirname, 'node_modules'),
		],
	},
	externals: {
		"jquery": "jQuery",
	},
	optimization: {
		splitChunks: {
			chunks: 'async',
			minSize: 20000,
			minRemainingSize: 0,
			minChunks: 1,
			maxAsyncRequests: 30,
			maxInitialRequests: 30,
			enforceSizeThreshold: 50000,
			cacheGroups: {
				buffer: {
					test: /[\\/]node_modules[\\/](@turf\/buffer|turf-jsts)[\\/]/,
					name: 'buffer',
					chunks: 'all',
					priority: -5,
					reuseExistingChunk: true,
				},
				vendors: {
					test: /[\\/]node_modules[\\/](@turf)[\\/]/,
					name: 'vendors',
					chunks: 'all',
					priority: -10,
					reuseExistingChunk: true,
				},
				default: {
					minChunks: 2,
					priority: -20,
					reuseExistingChunk: true,
				},
			},
		},
		minimize: false, // Switch to true for production
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