from django.test import TestCase
from django.contrib.auth.hashers import make_password, check_password, get_hasher
from django.utils.crypto import pbkdf2, get_random_string
from hashlib import sha256
from base64 import b64encode

from copy import deepcopy

from django_pph.utils import cache, constant_time_compare
from django_pph.management.commands.initialize_pph_context import \
        Command as pph_init



def make(password):
    return make_password(password, hasher='pph')


def make_share(password):
    return make_password(password, '$easalt', hasher='pph')


def check(password, encoded):
    return check_password(password, encoded,  preferred='pph')

def reset_hasher_state(hasher, backup):
    cache.clear()
    hasher.data['secret'] = backup['secret']
    hasher.data['thresholdlesskey'] = backup['thresholdlesskey']
    hasher.data['shamirsecretobj'] = backup['shamirsecretobj']
    hasher.data['is_unlocked'] = backup['is_unlocked']
    hasher.share_data['nextavailableshare'] = 1
    hasher.update()
    

class PolyPasswordHasherTestCase(TestCase):

    hasher = get_hasher('pph')
    # we'll backup everything to avoid some tests from interfering with
    # another
    hasher.load()
    hasherbackup = deepcopy(hasher.data)

    def setUp(self):
        reset_hasher_state(self.hasher, self.hasherbackup)

    def test_hasher(self):

        password1 = make_share('password1')
        password2 = make_share('password2')
        password3 = make_share('password3')
        
        self.assertTrue(password1.startswith('pph$1'))
        self.assertTrue(password2.startswith('pph$2'))
        self.assertTrue(password3.startswith('pph$3'))

        self.assertTrue(check('password1', password1))
        self.assertTrue(check('password2', password2))
        self.assertTrue(check('password3', password3))

        self.assertLess(len(password1), 128)
        self.assertLess(len(password2), 128)
        self.assertLess(len(password3), 128)


    def test_total_shares(self):

        # TODO: Any higher range breaks shamirsecret.compute_share
        for i in range(253):
            raw = 'password%d' % i
            password = make(raw)
            self.assertTrue(check(raw, password))
            self.assertLess(len(password), 128)

    # We create a brand new store, lock it and unlock it. We expect to have
    # the secret back at the end of this function.
    def test_unlock_store(self):

        reset_hasher_state(self.hasher, self.hasherbackup)
        
        password1 = make_share('password1')
        password2 = make_share('password2')
        password3 = make_share('password3')
        password4 = make_share('password4')
        password5 = make_share('password5')

        # We backup the secret to compare against it upon recombination
        secret_backup = self.hasher.data['secret']
        self.hasher.update(secret=None)

        self.assertTrue(check('password1', password1))
        self.assertTrue(check('password2', password2))
        self.assertTrue(check('password3', password3))
        self.assertTrue(check('password4', password4))
        self.assertTrue(check('password5', password5))

        # with a threshold of 5, at this point we should have the secret back
        self.assertTrue(self.hasher.data['secret'] is not None)
        self.assertTrue(self.hasher.data['secret'] == secret_backup)

    # We will do all of the pertinent thresholdless movements in this test:
    #   * Create a thresholdless hash with the context unlocked
    #   * Fail to provide a new hash after locking the store
    #   * Provide partial verification for thresholdless account
    #   * Provide new creation capabilities after re-unlocking
    #   * Provide verification capabilities after unlocking (original hash)
    def test_thresholdless_hash(self):

        # These are threshold accounts for the unlocking phase
        password1 = make_share('password1')
        password2 = make_share('password2')
        password3 = make_share('password3')
        password4 = make_share('password4')
        password5 = make_share('password5')

        thresholdless1 = make('thresholdless1')

        # we lock the store forcefully
        self.hasher.update(
            secret=None,
            thresholdlesskey=None,
            is_unlocked=False
        )

        # NOTICE: since we are now able to provide hashes even when the context
        # is unlocked, I removed the "self.assertRaises".

        # partial verification
        self.assertTrue(check('thresholdless1', thresholdless1))

        # unlock the store
        self.assertTrue(check('password1', password1))
        self.assertTrue(check('password2', password2))
        self.assertTrue(check('password3', password3))
        self.assertTrue(check('password4', password4))
        self.assertTrue(check('password5', password5))

        # get a new hash
        thresholdless2 = make('thresholdless2')

        # verify the passwords
        self.assertTrue(check('thresholdless1', thresholdless1))
        self.assertTrue(check('thresholdless2', thresholdless2))

    def test_partial_verfication(self):

        password1 = make_share('password1')

        # Forcefully lock the context

        self.hasher.update(secret=None)

        # now try to provide partial verification
        self.assertTrue(check('password1', password1))

    def test_locked_hashes(self):

        # Forcefully lock the context and flush everything related to
        # accounts
        self.hasher.update(secret=None, thresholdlesskey=None,
                is_unlocked=False)
        cache.clear()

        password1 = make_share('password1') # get an account

        algorithm, sharenumber, iterations, salt, passhash = \
                password1.split('$',4)
        passhash = passhash.encode('ascii').strip()

        iterations = int(iterations)

        self.assertTrue('pph' == algorithm)
        self.assertTrue(sharenumber.startswith('-'))
        
        # now let's do a plain pbkdf2 hash and compare the results
        proposed_hash = pbkdf2('password1', salt, iterations, digest=sha256)
        proposed_hash = b64encode(proposed_hash)

        self.assertTrue(proposed_hash == passhash)

    # this test will try to promote threhshold and thresholdless hashes. We
    # Expect to be able to promote thresholdless regardless of lock status and
    # fail to promote already threshold accounts
    def test_promote_hash(self):

        
        password1 = make('password1')
        promoted_password1 = self.hasher.promote_hash(password1)

        algorithm, sharenumber, iterations, salt, hash = \
                promoted_password1.split('$', 4)

        self.assertTrue(password1 != promoted_password1)
        self.assertTrue(password1.split('$',4)[1] != sharenumber)
        self.assertTrue(not sharenumber.startswith('-'))

        # verify that we would be able to login with the proper password
        self.assertTrue(check('password1', promoted_password1))

        threshold_password1 = make_share('password1')
        with self.assertRaises(AssertionError):
            self.hasher.promote_hash(threshold_password1)


        # lock the context forcefully
        self.hasher.update(secret=None, thresholdlesskey=None,
                is_unlocked=False)

        # make a locked thresholdless password
        password2 = make('password2')

        # promote the thresholdless password
        promoted_password2 = self.hasher.promote_hash(password2)
        algorithm ,sharenumber, iterations, salt, hash = \
                promoted_password2.split('$', 4)

        self.assertTrue(password2.split('$',4)[1] != sharenumber)

        # since the context is locked and the original account is locked, 
        self.assertTrue(password2.split('$',4)[4] == hash)

        # verify that we would be able to login with the proper password
        self.assertTrue(check('password2', promoted_password2))

        # test it fails with a (now) threshold account. I will reutilize the
        # produced hash
        with self.assertRaises(AssertionError):
                self.hasher.promote_hash(promoted_password2)


    # This tests for the demote function, which turns a threshold password
    # into a thresholdless password.
    def test_demote_user(self):

        password1 = make_share('password1')
        demoted_password1 = self.hasher.demote_hash(password1)

        algorithm, sharenumber, iterations, salt, hash = \
                demoted_password1.split('$', 4)

        self.assertTrue(password1 != demoted_password1)
        self.assertTrue(sharenumber == '0')
        self.assertTrue(not sharenumber.startswith('-'))

        # verify that we would be able to login with the proper password
        self.assertTrue(check('password1', demoted_password1))

        # We shouldn't attempt to demote an already thresholdless password
        thless_password = make('password')
        with self.assertRaises(AssertionError):
            self.hasher.demote_hash(thless_password)

        # lock the context forcefully
        self.hasher.update(secret=None, thresholdlesskey=None,
                is_unlocked=False)

        # make a locked threshold password
        password2 = make_share('password2')

        # demote threshhold.
        demoted_password2 = self.hasher.demote_hash(password2)

        algorithm, sharenumber, iterations, salt, hash = \
                demoted_password2.split('$', 4)

        self.assertTrue(password2 != demoted_password2)
        self.assertTrue(sharenumber == '-0')
        
        # check login
        self.assertTrue(check('password2', demoted_password2))

        # create a thresholdless account and try to demote it
        thless_password2 = make('password')
        with self.assertRaises(AssertionError):
            self.hasher.demote_hash(thless_password2)

        # try to demote our original threshold account with a locked context
        with self.assertRaises(AssertionError):
            self.hasher.demote_hash(password1)


    # we attempt to test a "migration" procedure using the hasher instance. 
    # To test this, we will create the has both ways: fist from the original 
    # data and one by updatng our resulting hash.
    def test_update_hash_threshold(self): 
  
        # we will remove the $ because we are going to create the entry
        # artificially
        salt = get_random_string(6).strip('$')

        password = 'password1'
        iterations = 12000

        pbkdf2_encoded_password = pbkdf2(password, salt, iterations,
                digest=sha256)

        pbkdf2_encoded_password = b64encode(pbkdf2_encoded_password)

        polyhash, sharenumber = self.hasher.update_hash_threshold(
                pbkdf2_encoded_password)

        password_string = "{0}${1}${2}${3}${4}".format('pph', sharenumber,
                iterations, salt, polyhash)

        # TODO we should cehck whether they can provide partial verification
        self.assertTrue(check(password, password_string))
    


    # we attempt to test a "migration" procedure using the hasher instance.To
    # test this, we will create the hash both ways: from original data and
    # through update_hash_thresholdless and compare the results
    def test_update_hash_thresholdless(self):

        # we will strip $ to avoid creating a threshold account by accident
        salt = get_random_string(6).strip('$')

        password = 'password1'
        iterations = 12000

        pbkdf2_encoded_password = pbkdf2(password, salt, iterations,
                digest=sha256)

        pbkdf2_encoded_password = b64encode(pbkdf2_encoded_password)

        password_normally = make_password(password, salt, hasher='pph')
        password_normally = password_normally.split('$',4)[4]

        password_through_update = self.hasher.update_hash_thresholdless(
                pbkdf2_encoded_password)
       
        self.assertTrue(constant_time_compare(password_normally,
            password_through_update))

        # finally, try to log in with our updated password
        pass_string = "{0}${1}${2}${3}${4}".format('pph', 0, iterations, salt,
                password_through_update)
    
        # TODO we should cehck whether they can provide partial verification
        self.assertTrue(check(password, pass_string))


    # this function tests the secret creation capabilities. We will generate
    # a series of valid and invalid secrets and expect the function to be able
    # to discern between them 
    def test_secret_creation_and_verification(self):

        # create a valid secret
        valid_secret = pph_init().create_secret() 

        # invalid secret[0] will have its first bit inverted.
        # TODO this looks ugly
        if isinstance(valid_secret[0], int):
            byte_to_negate = valid_secret[0]
            byte_to_negate = byte_to_negate ^ 0x1
            byte_to_negate = bytes(byte_to_negate)
        else:
            byte_to_negate = str(ord(valid_secret[0]) ^ 0x1)

        invalid_secret = byte_to_negate + valid_secret[1:]


        # now lets verify both
        self.assertTrue(self.hasher.verify_secret(valid_secret))
        self.assertTrue(not self.hasher.verify_secret(invalid_secret))

    # We will attempt to create a threshold number of threshold accounts. After
    # this, we will attempt recombination with one of the log-ins being a 
    # partial_verification colission. After this, we will attempt recombination
    # by logging in threshold + 1 accounts
    def test_recombination_with_wrong_shares(self):

        # this is a threshold-sensitive test, so we will ensure it's the value
        # we need
        self.assertTrue(self.hasher.threshold == 3)

        # create conflicting hash
        # Consider that these credentials only work for pbkdf2_sha256 and 
        # 12000 iterations
        PASSWORD = 'santiago'
        COLISSION_PASSWORD = 'jojo'
        SALT = '4IPwS2gg0Oo1'
        password_with_colission = make_password('santiago', '$4IPwS2gg0Oo1', 
                hasher='pph')

        # make a threshold number of accounts for unlocking
        password1 = make_share('password1')
        password2 = make_share('password2')
        password3 = make_share('password3')

        # lock the context now.
        self.hasher.update(
                secret = None,
                thresholdlesskey = None,
                is_unlocked = None)

        # try to recover the secret, use the colission share to make a conflict
        self.assertTrue(check(COLISSION_PASSWORD, password_with_colission))

        self.assertTrue(check('password1', password1))
        self.assertTrue(check('password2', password2))

        # should be unlocked, if the first password was correct
        self.assertTrue(not self.hasher.data['is_unlocked'])

        # should be able to unlock with one more login
        self.assertTrue(check('password3', password3))
        self.assertTrue(self.hasher.data['is_unlocked'])

