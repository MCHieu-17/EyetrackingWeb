# k6 summary

scenario: outline

- http_req_sending: max=0.085, p(90)=0.069, p(95)=0.076, p(99)=0.083, avg=0.048, min=0.037, med=0.043
- http_req_waiting: p(99)=31.318, avg=10.784, min=6.920, med=9.762, max=35.868, p(90)=11.325, p(95)=13.119
- vus: min=1.000, max=1.000
- iterations: count=20.000, rate=4.716
- http_req_duration: p(99)=31.449, avg=10.973, min=7.159, med=9.945, max=35.964, p(90)=11.520, p(95)=13.387
- http_req_duration{expected_response:true}: p(95)=13.387, p(99)=31.449, avg=10.973, min=7.159, med=9.945, max=35.964, p(90)=11.520
- http_req_receiving: min=0.058, med=0.134, max=0.209, p(90)=0.199, p(95)=0.202, p(99)=0.208, avg=0.141
- http_req_blocked: p(99)=0.091, avg=0.016, min=0.010, med=0.011, max=0.109, p(90)=0.014, p(95)=0.019
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_failed: rate=0.000
- http_req_connecting: p(95)=0.004, p(99)=0.063, avg=0.004, min=0.000, med=0.000, max=0.077, p(90)=0.000
