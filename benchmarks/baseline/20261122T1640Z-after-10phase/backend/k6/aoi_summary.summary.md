# k6 summary

scenario: aoi_summary

- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: max=0.120, p(90)=0.000, p(95)=0.000, p(99)=0.116, avg=0.004, min=0.000, med=0.000
- http_req_waiting: p(99)=228.747, avg=189.069, min=159.996, med=184.046, max=234.202, p(90)=218.414, p(95)=222.411
- http_req_receiving: p(95)=0.446, p(99)=0.726, avg=0.227, min=0.083, med=0.205, max=0.864, p(90)=0.394
- iterations: rate=5.118, count=52.000
- http_req_blocked: avg=0.017, min=0.002, med=0.011, max=0.163, p(90)=0.015, p(95)=0.034, p(99)=0.155
- http_req_failed: rate=0.000
- vus: min=2.000, max=2.000
- http_req_duration{expected_response:true}: p(90)=218.676, p(95)=222.600, p(99)=229.070, avg=189.350, min=160.287, med=184.296, max=234.453
- http_req_sending: min=0.011, med=0.052, max=0.099, p(90)=0.075, p(95)=0.080, p(99)=0.096, avg=0.053
- http_req_duration: p(99)=229.070, avg=189.350, min=160.287, med=184.296, max=234.453, p(90)=218.676, p(95)=222.600
