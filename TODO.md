# TODO - Spreadsheet Q&A Assistant

## ✅ Completed (v2.3.0)

### Critical Fixes
- [x] Fix embedding dimension mismatch when switching models
- [x] Auto-detect and recreate vector stores for different dimensions
- [x] Fix quick questions to immediately trigger LLM processing
- [x] Add metadata tracking for vector stores

### Model Selection
- [x] Hardware detection (RAM, CPU, GPU)
- [x] Apple Silicon chip-specific detection (M1/M2/M3)
- [x] Smart model recommendations based on hardware
- [x] Live download progress with real-time output
- [x] Model categorization by size
- [x] Visual indicators for installed models

### UI/UX Improvements
- [x] Create a web UI as an alternative to terminal interface
- [x] Model Settings panel with hardware details
- [x] Clear cache button for vector store
- [x] Warning messages for model changes
- [x] Progress bars for downloads
- [x] Better model organization in dropdowns
- [x] Quick questions in main chat area
- [x] Professional dark theme

## 🚧 High Priority

### Core Functionality
- [ ] Add support for Excel files (.xlsx, .xls)
- [ ] Implement streaming responses for large datasets
- [ ] Add data validation and error handling for malformed CSVs
- [ ] Support for multiple sheets/tabs in one session
- [ ] Add ability to save/load conversation history

### Performance
- [ ] Optimize embedding generation for datasets > 10k rows
- [ ] Implement batching for large file processing
- [ ] Add progress indicators for data loading (beyond model downloads)
- [ ] Cache embeddings for frequently accessed sheets

### User Experience
- [ ] Add data preview before processing
- [ ] Implement query templates for common questions
- [ ] Add export functionality for query results
- [ ] Better error messages with suggested fixes

## 📋 Medium Priority

### Features
- [ ] Support for more file formats (JSON, Parquet, etc.)
- [ ] Multi-language support for non-English datasets
- [ ] Custom column type detection and handling
- [ ] Query history and analytics
- [ ] Collaborative features for team use

### Cloud Mode (Future Release)
- [ ] Cloud vector storage with Pinecone
- [ ] Team collaboration features
- [ ] Saved queries and insights
- [ ] API endpoints for integration
- [ ] User authentication

### Integration
- [ ] Slack bot integration
- [ ] Microsoft Teams integration
- [ ] Jupyter notebook extension
- [ ] VS Code extension
- [ ] Direct database connections (PostgreSQL, MySQL)

## 🔮 Low Priority

### Advanced Features
- [ ] MLX model integration for Apple Silicon (infrastructure ready)
- [ ] Custom model fine-tuning on user data
- [ ] Automated report generation
- [ ] Data visualization generation
- [ ] Natural language data transformations

### Developer Experience
- [ ] Comprehensive test suite
- [ ] Performance benchmarks
- [ ] Plugin architecture
- [ ] TypeScript SDK
- [ ] Example notebooks

## 💡 Ideas for Future

1. **Smart Caching**: Cache frequently asked questions
2. **Query Suggestions**: AI-powered query recommendations
3. **Voice Interface**: Ask questions using speech
4. **Mobile App**: iOS/Android companion apps
5. **Data Connectors**: Salesforce, HubSpot, Google Analytics
6. **AI Insights**: Proactive pattern detection and alerts
7. **Export to BI Tools**: Integration with Tableau, PowerBI

## 🐛 Known Issues

1. **Large Files**: Performance degrades with files > 100MB
2. **Complex Queries**: Some nested queries may timeout
3. **Memory Usage**: High memory usage with large models
4. **Windows**: Some terminal colors may not display correctly

## 🤝 Contributing

Want to help? Here are good first issues:
1. Add support for Excel files
2. Improve error messages
3. Add data visualization options
4. Write comprehensive tests
5. Improve documentation

To contribute:
1. Open an issue to discuss the approach
2. Create a pull request with your implementation
3. Update this TODO list as items are completed

## 📝 Notes

- Focus on stability and user experience
- Keep the app simple and intuitive
- Maintain backward compatibility
- Test thoroughly before releases
- Document all major changes

## 🎯 Next Release Focus (v2.4)

1. Excel file support
2. Streaming responses
3. Data visualization
4. Query templates
5. Performance optimizations for large files