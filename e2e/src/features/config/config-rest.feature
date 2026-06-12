@rest @config @P0
Feature: Global Config via REST
  Scenario: Global runtime config loads
    When I request the REST global config
    Then the REST global config should include server config and feature flags

  Scenario: Default agent config loads
    When I request the REST default agent config
    Then the REST default agent config should be an object

  Scenario: SPA server config loads
    When I request the SPA server config
    Then the SPA server config should include auth and feature flags
