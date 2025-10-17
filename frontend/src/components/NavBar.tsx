import { Flex, Heading, Spacer } from '@chakra-ui/react';
import { Link } from 'react-router-dom';

const NavBar = () => {
  return (
    <Flex as="header" align="center" py={4} px={{ base: 4, md: 8 }}>
      <Heading as={Link} to="/" size="md" letterSpacing="widest">
        Poker Analytics
      </Heading>
      <Spacer />
    </Flex>
  );
};

export default NavBar;
