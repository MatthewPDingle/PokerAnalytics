import { Flex, Heading, Spacer, Select, Text } from '@chakra-ui/react';
import { Link } from 'react-router-dom';

import { useActiveDataSource } from '../hooks/useActiveDataSource';

const NavBar = () => {
  const { sources, activeSourceKey, setActiveSourceKey, loading } = useActiveDataSource();

  const handleChange: React.ChangeEventHandler<HTMLSelectElement> = (event) => {
    const value = event.target.value.trim();
    setActiveSourceKey(value || null);
  };

  return (
    <Flex as="header" align="center" h="64px" px={{ base: 4, md: 8 }}>
      <Heading as={Link} to="/" size="md" letterSpacing="widest">
        Poker Analytics
      </Heading>
      <Spacer />
      {sources.length > 0 && (
        <Flex align="center" gap={2}>
          <Text fontSize="sm" color="whiteAlpha.700" whiteSpace="nowrap">
            Data Source
          </Text>
          <Select
            size="sm"
            maxW="220px"
            value={activeSourceKey ?? ''}
            onChange={handleChange}
            bg="blackAlpha.500"
            borderColor="whiteAlpha.400"
            isDisabled={loading}
          >
            {sources.map((source) => (
              <option key={source.key} value={source.key}>
                {source.key === 'drivehud' ? 'Ignition (DriveHUD)' : source.label}
              </option>
            ))}
          </Select>
        </Flex>
      )}
    </Flex>
  );
};

export default NavBar;
