# Portfolio Stocks Watching List System Improvement - Product Requirement Document

## Overview
- **Summary**: Restructure the portfolio_stocks database table to store only essential fields and implement dynamic data retrieval for financial metrics, enhancing CRUD operations and reducing redundant storage.
- **Purpose**: Create a more efficient and maintainable watching list system with up-to-date financial data by eliminating redundant stored calculations and implementing dynamic data retrieval.
- **Target Users**: Developers maintaining the OpenBB App and end users accessing portfolio stock information through the API.

## Goals
- Restructure portfolio_stocks table to store only essential persistent fields
- Implement dynamic data retrieval for financial metrics using obb.equity.price.quote
- Enhance CRUD operations to work with the new table structure
- Ensure data consistency between stored and dynamically generated fields
- Maintain backward compatibility with existing API endpoints

## Non-Goals (Out of Scope)
- Changing the overall API endpoint structure
- Modifying other database tables (equity_price_history, transactions, etc.)
- Implementing new authentication mechanisms
- Adding new portfolio management features beyond the specified improvements

## Background & Context
The current portfolio_stocks table stores both persistent data and calculated/retrieved financial metrics, leading to redundant storage and potential data inconsistency. The system should instead store only essential persistent fields and dynamically retrieve financial metrics on demand.

## Functional Requirements
- **FR-1**: Restructure portfolio_stocks table to store only essential fields (symbol, name, avg_cost, quantity, total_value)
- **FR-2**: Implement dynamic retrieval of financial metrics using obb.equity.price.quote
- **FR-3**: Implement calculation of strategy field using get_strategies function
- **FR-4**: Implement generation of tradingview field using get_tvlink function
- **FR-5**: Update CRUD operations to work with the new table structure
- **FR-6**: Ensure proper error handling for API calls with fallback values

## Non-Functional Requirements
- **NFR-1**: Maintain backward compatibility with existing API responses
- **NFR-2**: Ensure data consistency between stored and dynamically generated fields
- **NFR-3**: Implement proper validation for all input fields
- **NFR-4**: Ensure efficient API calls with appropriate caching

## Constraints
- **Technical**: Must use existing OpenBB platform functions (obb.equity.price.quote)
- **Dependencies**: Requires OpenBB platform integration for financial data retrieval

## Assumptions
- The obb.equity.price.quote function is available and returns the required financial metrics
- Existing API endpoints should continue to return the same data structure for compatibility
- Database migrations will be handled appropriately during implementation

## Acceptance Criteria

### AC-1: Table Structure Restructuring
- **Given**: The database schema is updated
- **When**: The portfolio_stocks table is modified
- **Then**: The table should only contain the essential fields: symbol, name, avg_cost, quantity, total_value
- **Verification**: `programmatic`

### AC-2: Dynamic Data Retrieval
- **Given**: An API call is made to retrieve portfolio stocks
- **When**: Financial data is needed
- **Then**: The system should call obb.equity.price.quote to retrieve current_price, fifty_two_week_low, fifty_two_week_high, dividend_yield, latest_dividend
- **Verification**: `programmatic`

### AC-3: Calculated Fields Implementation
- **Given**: A portfolio stock is retrieved
- **When**: Strategy and tradingview fields are needed
- **Then**: The system should calculate strategy using get_strategies and generate tradingview link using get_tvlink
- **Verification**: `programmatic`

### AC-4: CRUD Operations Enhancement
- **Given**: CRUD operations are performed on portfolio stocks
- **When**: Creating, reading, updating, or deleting stocks
- **Then**: Operations should work with the new table structure and incorporate dynamically retrieved fields
- **Verification**: `programmatic`

### AC-5: Error Handling
- **Given**: API calls to obb.equity.price.quote fail
- **When**: Financial data retrieval is attempted
- **Then**: The system should use fallback values and log the error
- **Verification**: `programmatic`

### AC-6: Testing
- **Given**: Unit tests are executed
- **When**: Testing the modified functionality
- **Then**: All tests should pass, including edge cases for missing data and API failures
- **Verification**: `programmatic`

## Open Questions
- [ ] How should database migrations be handled for existing data?
- [ ] What fallback values should be used when API calls fail?
- [ ] How frequently should financial data be refreshed?
- [ ] Should there be caching for the dynamically retrieved data?