# Contributing to AIC-ADE

Thank you for your interest in contributing to AIC-ADE!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch
4. Make your changes
5. Submit a pull request

## Development Setup

```bash
# Backend
cd aic-platform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../aic-ide
npm install
```

## Running Tests

```bash
# Backend tests
cd aic-platform
source venv/bin/activate
python -m pytest tests/ -q

# Frontend tests
cd ../aic-ide
npm test
```

## Code Style

- Python: Follow PEP 8
- TypeScript: Follow ESLint configuration
- Use meaningful variable names
- Add docstrings to public functions
- Write tests for new features

## Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all tests pass
4. Request review from maintainers

## Reporting Issues

- Use GitHub Issues
- Include reproduction steps
- Include environment details
- Include error messages

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
