# TODO

## High Priority

### Core Functionality
- [ ] Add support for Excel files (.xlsx, .xls)
- [ ] Implement streaming responses for large datasets
- [ ] Add data validation and error handling for malformed CSVs
- [ ] Support for multiple sheets/tabs in one session
- [ ] Add ability to save/load conversation history

### Performance
- [ ] Optimize embedding generation for datasets > 10k rows
- [ ] Implement batching for large file processing
- [ ] Add progress indicators for data loading
- [ ] Cache embeddings for frequently accessed sheets

### User Experience
- [ ] Create a web UI as an alternative to terminal interface
- [ ] Add data preview before processing
- [ ] Implement query templates for common questions
- [ ] Add export functionality for query results
- [ ] Better error messages with suggested fixes

## Medium Priority

### Features
- [ ] Support for more file formats (JSON, Parquet, etc.)
- [ ] Multi-language support for non-English datasets
- [ ] Custom column type detection and handling
- [ ] Query history and analytics
- [ ] Collaborative features for team use

### Cloud/API Improvements
- [ ] Add authentication to API endpoints
- [ ] Rate limiting and usage quotas
- [ ] Webhook support for data updates
- [ ] GraphQL API option
- [ ] OpenAPI/Swagger documentation

### Integration
- [ ] Slack bot integration
- [ ] Microsoft Teams integration
- [ ] Jupyter notebook extension
- [ ] VS Code extension
- [ ] Direct database connections (PostgreSQL, MySQL)

## Low Priority

### Advanced Features
- [ ] Custom model fine-tuning on user data
- [ ] Automated report generation
- [ ] Scheduled data refreshes
- [ ] Data visualization generation
- [ ] Natural language data transformations

### Developer Experience
- [ ] Automated tests suite
- [ ] Performance benchmarks
- [ ] Plugin architecture
- [ ] TypeScript SDK
- [ ] Example notebooks

## Ideas for Future

- **Voice Interface** - Ask questions using speech
- **Mobile App** - iOS/Android apps for on-the-go queries  
- **Data Connectors** - Salesforce, HubSpot, Google Analytics
- **AI Insights** - Proactive pattern detection and alerts
- **Export to BI Tools** - Integration with Tableau, PowerBI

## Contributing

Want to help? Pick any item from this list and:
1. Open an issue to discuss the approach
2. Create a pull request with your implementation
3. Update this TODO list as items are completed

Priority items that would have immediate impact:
- Excel file support
- Web UI
- Progress indicators
- Better error handling