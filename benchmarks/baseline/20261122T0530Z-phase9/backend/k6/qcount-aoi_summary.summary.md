# k6 summary

scenario: aoi_summary

- http_req_receiving: avg=0.360, min=0.097, med=0.217, max=1.188, p(90)=0.892, p(95)=1.087, p(99)=1.168
- http_req_waiting: min=160.357, med=177.446, max=221.321, p(90)=208.080, p(95)=217.183, p(99)=220.493, avg=181.961
- http_req_sending: avg=0.074, min=0.029, med=0.064, max=0.215, p(90)=0.104, p(95)=0.135, p(99)=0.199
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.087, p(90)=0.000, p(95)=0.004, p(99)=0.070
- http_req_duration{expected_response:true}: min=161.589, med=177.940, max=221.606, p(90)=208.583, p(95)=217.989, p(99)=220.883, avg=182.395
- vus: min=1.000, max=1.000
- http_req_duration: max=221.606, p(90)=208.583, p(95)=217.989, p(99)=220.883, avg=182.395, min=161.589, med=177.940
- http_req_blocked: med=0.011, max=0.116, p(90)=0.012, p(95)=0.018, p(99)=0.096, avg=0.016, min=0.004
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=2.608
