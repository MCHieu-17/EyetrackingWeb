# k6 summary

scenario: lesson_contents

- http_req_duration: med=9.582, max=23.152, p(90)=18.158, p(95)=19.382, p(99)=21.569, avg=11.158, min=2.943
- http_req_blocked: avg=0.014, min=0.002, med=0.011, max=0.137, p(90)=0.014, p(95)=0.018, p(99)=0.134
- http_req_duration{expected_response:true}: avg=11.158, min=2.943, med=9.582, max=23.152, p(90)=18.158, p(95)=19.382, p(99)=21.569
- iterations: count=238.000, rate=23.548
- http_req_sending: min=0.007, med=0.041, max=0.156, p(90)=0.055, p(95)=0.065, p(99)=0.118, avg=0.042
- http_req_receiving: p(90)=0.201, p(95)=0.238, p(99)=0.359, avg=0.093, min=0.009, med=0.061, max=0.548
- vus: min=5.000, max=5.000
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.105, avg=0.002, min=0.000, med=0.000, max=0.106
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_waiting: p(95)=19.216, p(99)=21.258, avg=11.023, min=2.891, med=9.441, max=22.905, p(90)=18.056
- http_req_failed: rate=0.000
