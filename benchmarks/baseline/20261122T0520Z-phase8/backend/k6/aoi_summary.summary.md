# k6 summary

scenario: aoi_summary

- vus: max=2.000, min=2.000
- http_req_blocked: avg=0.017, min=0.003, med=0.011, max=0.144, p(90)=0.016, p(95)=0.034, p(99)=0.137
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_sending: p(95)=0.081, p(99)=0.115, avg=0.056, min=0.015, med=0.056, max=0.129, p(90)=0.075
- http_req_connecting: p(99)=0.099, avg=0.004, min=0.000, med=0.000, max=0.103, p(90)=0.000, p(95)=0.000
- http_req_duration: med=191.653, max=235.914, p(90)=221.742, p(95)=227.665, p(99)=234.957, avg=194.789, min=167.417
- http_req_duration{expected_response:true}: p(99)=234.957, avg=194.789, min=167.417, med=191.653, max=235.914, p(90)=221.742, p(95)=227.665
- http_req_receiving: med=0.186, max=0.831, p(90)=0.515, p(95)=0.586, p(99)=0.770, avg=0.244, min=0.100
- iterations: count=52.000, rate=5.055
- http_req_waiting: p(99)=234.197, avg=194.489, min=167.239, med=191.469, max=235.020, p(90)=221.416, p(95)=227.441
- http_req_failed: rate=0.000
