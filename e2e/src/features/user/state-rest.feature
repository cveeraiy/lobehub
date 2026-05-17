@rest @user @P0
Feature: User State via REST
  Background:
    Given I am logged in with a session

  @USER-REST-001
  Scenario: App loads user state on startup
    When I request the REST user state
    Then the REST user state should include the test user profile

  @USER-REST-002
  Scenario: User updates display name and it persists
    When I update the REST user display name to "E2E REST User"
    And I request the REST user state
    Then the REST user state display name should be "E2E REST User"

  @USER-REST-003
  Scenario: User changes language model settings and they persist
    When I update REST user settings with language model provider "openai"
    And I request the REST user state
    Then the REST user settings should include language model provider "openai"

  @USER-REST-004
  Scenario: User completes onboarding step and it persists
    When I update the REST onboarding state to step 2
    And I request the REST user state
    Then the REST onboarding state should be step 2

  @USER-REST-005
  Scenario Outline: Settings pages render without errors
    When I navigate to "/settings/<tab>"
    Then the response status should be less than 400
    And the page should load without errors
    And I should see the page body

    Examples:
      | tab          |
      | about        |
      | agent        |
      | provider/all |
