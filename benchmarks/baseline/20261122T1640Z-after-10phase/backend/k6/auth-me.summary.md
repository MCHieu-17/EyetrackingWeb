# k6 summary

scenario: me

- http_req_duration{expected_response:true}: med=7.741, max=10.256, p(90)=9.662, p(95)=9.881, p(99)=10.177, avg=7.527, min=1.840
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_blocked: avg=0.014, min=0.003, med=0.011, max=0.119, p(90)=0.015, p(95)=0.020, p(99)=0.073
- http_req_duration: avg=7.527, min=1.840, med=7.741, max=10.256, p(90)=9.662, p(95)=9.881, p(99)=10.177
- http_req_receiving: med=0.106, max=0.195, p(90)=0.144, p(95)=0.152, p(99)=0.182, avg=0.093, min=0.024
- http_req_failed: rate=0.000
- iterations: count=48.000, rate=4.795
- http_req_connecting: med=0.000, max=0.084, p(90)=0.000, p(95)=0.000, p(99)=0.045, avg=0.002, min=0.000
- http_req_waiting: p(90)=9.513, p(95)=9.715, p(99)=9.991, avg=7.391, min=1.782, med=7.561, max=10.064
- http_req_sending: avg=0.043, min=0.012, med=0.041, max=0.058, p(90)=0.052, p(95)=0.056, p(99)=0.058
- vus: min=1.000, max=1.000
